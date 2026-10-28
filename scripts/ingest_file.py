"""Индексация файлов из data/raw/ → data/storage/.

Поддерживаемые форматы: PDF, DOCX, TXT, MD, HTML, CSV, XLSX, изображения (OCR).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from src.core.config import settings
from src.core.db import AsyncSessionLocal
from src.core.db.models import Document
from src.core.rag.embeddings import build_embedder
from src.core.rag.ingest import ingest_text
from src.core.storage import get_storage


# --- Экстракторы по формату ---

def _extract_pdf(path: Path) -> tuple[str, dict]:
    import pymupdf
    doc = pymupdf.open(path)
    parts = [page.get_text() for page in doc]
    return "\n\n".join(parts).strip(), {"pages": len(doc)}


def _extract_txt(path: Path) -> tuple[str, dict]:
    return path.read_text(encoding="utf-8", errors="replace"), {}


def _extract_html(path: Path) -> tuple[str, dict]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(
        path.read_text(encoding="utf-8", errors="replace"), "html.parser"
    )
    for tag in soup(["script", "style", "nav", "footer", "noscript", "aside"]):
        tag.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    return soup.get_text("\n", strip=True), {"title": title}


def _extract_docx(path: Path) -> tuple[str, dict]:
    from docx import Document as DocxDocument
    doc = DocxDocument(str(path))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    # Таблицы в DOCX — отдельно, часто важны
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return "\n\n".join(parts), {"paragraphs": len(parts)}


def _extract_csv(path: Path) -> tuple[str, dict]:
    """
    CSV превращаем в построчный текст: «колонка1: значение1; колонка2: значение2».
    Так каждая строка становится осмысленным чанком (важно для расписаний!).
    """
    import csv
    lines: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        return "", {}

    header = rows[0]
    for row in rows[1:]:
        pairs = [f"{h.strip()}: {v.strip()}" for h, v in zip(header, row) if v.strip()]
        if pairs:
            lines.append("; ".join(pairs))
    return "\n".join(lines), {"rows": len(lines), "columns": len(header)}


def _extract_xlsx(path: Path) -> tuple[str, dict]:
    """Excel — построчно, по листам. Расписания часто в .xlsx."""
    from openpyxl import load_workbook
    wb = load_workbook(str(path), data_only=True, read_only=True)
    lines: list[str] = []
    for sheet in wb.worksheets:
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            continue
        header = [str(c) if c is not None else "" for c in rows[0]]
        for row in rows[1:]:
            pairs = [
                f"{h}: {v}"
                for h, v in zip(header, row)
                if v is not None and str(v).strip()
            ]
            if pairs:
                lines.append(f"[{sheet.title}] " + "; ".join(pairs))
    return "\n".join(lines), {"sheets": len(wb.worksheets)}


def _extract_image(path: Path) -> tuple[str, dict]:
    """JPG/PNG — OCR через Tesseract. Для сканов таблиц/расписаний."""
    import pytesseract
    from PIL import Image
    img = Image.open(path)
    text = pytesseract.image_to_string(img, lang="rus+eng")
    return text.strip(), {"size": img.size}


# --- Диспетчер ---
_EXTRACTORS = {
    ".pdf":  _extract_pdf,
    ".txt":  _extract_txt,
    ".md":   _extract_txt,
    ".html": _extract_html,
    ".htm":  _extract_html,
    ".docx": _extract_docx,
    ".csv":  _extract_csv,
    ".xlsx": _extract_xlsx,
    ".xls":  _extract_xlsx,       # openpyxl не читает .xls — см. «Подводные камни»
    ".jpg":  _extract_image,
    ".jpeg": _extract_image,
    ".png":  _extract_image,
}


def extract_text(path: Path) -> tuple[str, dict]:
    extractor = _EXTRACTORS.get(path.suffix.lower())
    if extractor is None:
        raise ValueError(f"Unsupported format: {path.suffix}")
    return extractor(path)


# --- Основной сценарий (почти как раньше) ---
async def ingest_one(inbox_path: Path, embedder) -> None:
    if not inbox_path.exists():
        raise FileNotFoundError(inbox_path)

    storage = get_storage()
    text, meta = extract_text(inbox_path)

    index_text = text or f"Документ {inbox_path.name}. Файл доступен для скачивания."

    # source_type: pdf/dox → document, csv/xlsx → schedule (если расписание),
    # images/сканы без текста → always_attach
    source_type = _guess_source_type(inbox_path, text)
    always_attach = not text or inbox_path.suffix.lower() in {".jpg", ".png"}

    async with AsyncSessionLocal() as db:
        result = await ingest_text(
            db,
            title=inbox_path.stem,
            text=index_text,
            source_type=source_type,
            external_id=inbox_path.name,
            meta={**meta, "always_attach": always_attach, "original_ext": inbox_path.suffix},
            embedder=embedder,
            settings=settings,
        )
        doc = await db.get(Document, result["document_id"])

        if doc.file_path and await storage.exists(doc.file_path):
            storage_key = doc.file_path
        else:
            storage_key = f"documents/{doc.id}/{inbox_path.name}"
            await storage.save(storage_key, inbox_path)
            doc.file_path = storage_key
            doc.file_mime = _mime_for(inbox_path.suffix)
            doc.file_size = inbox_path.stat().st_size
            doc.file_name = inbox_path.name

        await db.commit()
        print(
            f"[ok] doc_id={doc.id} status={result['status']} "
            f"chunks={result['chunks_created']} -> {storage_key}"
        )

    inbox_path.unlink()


def _guess_source_type(path: Path, text: str) -> str:
    """Простая эвристика: расписание → schedule, остальное → document."""
    name = path.stem.lower()
    if any(w in name for w in ("расписан", "schedule", "timetable")):
        return "schedule"
    if any(w in name for w in ("приём", "прием", "admission")):
        return "admission"
    return "document"


def _mime_for(suffix: str) -> str:
    return {
        ".pdf":  "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".csv":  "text/csv",
        ".txt":  "text/plain",
        ".md":   "text/markdown",
        ".html": "text/html",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png":  "image/png",
    }.get(suffix.lower(), "application/octet-stream")


# --- CLI ---
async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    embedder = build_embedder(settings)
    inbox = Path(settings.raw_dir)

    if args.all:
        targets = [p for p in inbox.iterdir() if p.is_file() and not p.name.startswith(".")]
        if not targets:
            print(f"[info] {inbox} пуст")
            return
    elif args.path:
        targets = [Path(args.path)]
    else:
        parser.error("Укажите путь или --all")

    for path in targets:
        try:
            await ingest_one(path, embedder)
        except Exception as exc:
            print(f"[error] {path.name}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
