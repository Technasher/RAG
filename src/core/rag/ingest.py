from __future__ import annotations

import hashlib

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.db.models import Chunk, Document, DocumentStatus
from src.core.rag.chunker import RecursiveChunker
from src.core.rag.embeddings import EmbeddingProvider
from src.core.rag.exceptions import IngestionError

from bs4 import BeautifulSoup


async def ingest_text(
        db: AsyncSession,
        *,
        title: str,
        text: str,
        source_type: str = "web",
        source_url: str | None = None,
        external_id: str | None = None,
        meta: dict | None = None,
        embedder: EmbeddingProvider,
        settings: Settings,
) -> dict:
    """
    Индексирует один документ. Возвращает {document_id, status, chunks_created}.
    """
    if not text.strip():
        raise IngestionError("Empty text")

    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    # 1. Upsert документа
    existing: Document | None = None
    if external_id:
        stmt = select(Document).where(
            Document.source_type == source_type,
            Document.external_id == external_id,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing and existing.content_hash == content_hash:
        return {
            "document_id": existing.id,
            "status": "skipped",
            "chunks_created": 0,
        }

    if existing:
        doc = existing
        doc.title = title
        doc.source_url = source_url
        doc.meta = meta or {}
        doc.content_hash = content_hash
        doc.status = DocumentStatus.PENDING
        # удаляем старые чанки (каскадно не сработает при update)
        for old_chunk in list(doc.chunks):
            await db.delete(old_chunk)
        await db.flush()
    else:
        doc = Document(
            title=title,
            source_type=source_type,
            source_url=source_url,
            external_id=external_id,
            meta=meta or {},
            content_hash=content_hash,
            status=DocumentStatus.PENDING,
        )
        db.add(doc)
        await db.flush()

    # 2. Чанкинг
    chunker = RecursiveChunker(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    text_chunks = chunker.split(text, base_meta={"title": title})

    if not text_chunks:
        doc.status = DocumentStatus.FAILED
        await db.commit()
        raise IngestionError("No chunks produced")

    # 3. Эмбеддинги (батчем — быстрее и дешевле)
    try:
        embeddings = await embedder.embed_many([c.content for c in text_chunks])
    except Exception as exc:
        doc.status = DocumentStatus.FAILED
        await db.commit()
        raise IngestionError(f"Embedding failed: {exc}") from exc

    # 4. Сохраняем чанки
    for tc, emb in zip(text_chunks, embeddings):
        db.add(
            Chunk(
                document_id=doc.id,
                chunk_index=tc.index,
                content=tc.content,
                embedding=emb,
                meta=tc.meta,
                token_count=len(tc.content) // 4,  # грубая оценка
            )
        )

    doc.status = DocumentStatus.INDEXED
    await db.commit()

    return {
        "document_id": doc.id,
        "status": "updated" if existing else "created",
        "chunks_created": len(text_chunks),
    }


async def ingest_url(
        db: AsyncSession,
        *,
        url: str,
        source_type: str = "web",
        meta: dict | None = None,
        embedder: EmbeddingProvider,
        settings: Settings,
) -> dict:
    """Fetch → extract text → ingest_text."""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            html = r.text
    except Exception as exc:
        raise IngestionError(f"Failed to fetch {url}: {exc}") from exc

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n", strip=True)
    title = (soup.title.string.strip() if soup.title and soup.title.string else url)

    return await ingest_text(
        db,
        title=title,
        text=text,
        source_type=source_type,
        source_url=url,
        external_id=url,
        meta=meta or {},
        embedder=embedder,
        settings=settings,
    )
