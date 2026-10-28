"""Индексация PDF из data/raw/ → data/storage/.

Использование:
    python -m scripts.ingest_pdf data/raw/schedule.pdf
    python -m scripts.ingest_pdf --all          # все файлы из inbox
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from pathlib import Path

from src.core.config import settings
from src.core.db import AsyncSessionLocal
from src.core.db.models import Document
from src.core.rag.embeddings import build_embedder
from src.core.rag.ingest import ingest_text
from src.core.storage import get_storage


# --- Извлечение текста (заглушка; OCR добавите позже) ---
def extract_pdf_text(path: Path) -> tuple[str, dict]:
    """Возвращает (text, meta). Для сканов text может быть коротким."""
    try:
        import pymupdf
        doc = pymupdf.open(path)
        parts = [page.get_text() for page in doc]
        text = "\n\n".join(parts).strip()
        return text, {"pages": len(doc)}
    except Exception as exc:
        print(f"[warn] cannot extract text from {path.name}: {exc}")
        return "", {}


# --- Основной сценарий ---
async def ingest_one(inbox_path: Path, embedder) -> None:
    if not inbox_path.exists():
        raise FileNotFoundError(inbox_path)

    storage = get_storage()
    text, meta = extract_pdf_text(inbox_path)

    # Если текста нет (скан) — индексируем хотя бы метаданные,
    # чтобы документ можно было найти и прикрепить файл.
    index_text = text or f"Документ {inbox_path.name}. Файл доступен для скачивания."

    async with AsyncSessionLocal() as db:
        # 1. Идемпотентная индексация (content_hash)
        result = await ingest_text(
            db,
            title=inbox_path.stem,
            text=index_text,
            source_type="pdf_schedule" if not text else "document",
            external_id=str(inbox_path.name),
            meta={**meta, "always_attach": not text},
            embedder=embedder,
            settings=settings,
        )
        doc = await db.get(Document, result["document_id"])

        # 2. Если файл уже в storage и запись цела — пропускаем
        if doc.file_path and await storage.exists(doc.file_path):
            storage_key = doc.file_path
            print(f"[skip] {inbox_path.name} already stored as {storage_key}")
        else:
            # 3. Сохраняем в storage: documents/{doc_id}/{original_name}
            storage_key = f"documents/{doc.id}/{inbox_path.name}"
            await storage.save(storage_key, inbox_path)
            doc.file_path = storage_key
            doc.file_mime = "application/pdf"
            doc.file_size = inbox_path.stat().st_size
            doc.file_name = inbox_path.name

        # 4. Commit ДО удаления из inbox — гарантия, что файл не потеряется
        await db.commit()

        print(
            f"[ok] doc_id={doc.id} status={result['status']} "
            f"chunks={result['chunks_created']} -> {storage_key}"
        )

    # 5. Только после успешного commit — убираем из inbox
    try:
        inbox_path.unlink()
    except OSError as exc:
        print(f"[warn] cannot unlink {inbox_path}: {exc}", file=sys.stderr)


# --- CLI ---
async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", help="Конкретный файл")
    parser.add_argument("--all", action="store_true", help="Все PDF из data/raw/")
    args = parser.parse_args()

    embedder = build_embedder(settings)
    inbox = Path(settings.raw_dir)

    if args.all:
        targets = sorted(inbox.glob("*.pdf"))
        if not targets:
            print(f"[info] {inbox} пуст — нечего индексировать")
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