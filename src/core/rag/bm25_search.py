from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.db.models import Chunk, Document
from src.core.rag.exceptions import RetrievalError
from src.core.rag.vector_search import SearchHit


async def bm25_search(
    db: AsyncSession,
    query: str,
    limit: int = 20,
) -> list[SearchHit]:
    """
    Лексический поиск по content_tsv с ранжированием ts_rank_cd.
    Аналог BM25 для PostgreSQL: учитывает частоту термина и близость слов.
    """
    query = (query or "").strip()
    if not query:
        return []

    # plainto_tsquery безопаснее to_tsquery: не падает на спецсимволах
    ts_query = func.plainto_tsquery(settings.fts_language, query)
    rank_expr = func.ts_rank_cd(Chunk.content_tsv, ts_query).label("rank")

    try:
        stmt = (
            select(Chunk, Document, rank_expr)
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.content_tsv.op("@@")(ts_query))
            .where(Document.status == "INDEXED")
            .order_by(rank_expr.desc())
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()
    except Exception as exc:
        raise RetrievalError(f"BM25 search failed: {exc}") from exc

    return [
        SearchHit(
            chunk_id=chunk.id,
            document_id=doc.id,
            content=chunk.content,
            title=doc.title,
            url=doc.source_url,
            rank=rank,
            raw_score=float(score),
            source="bm25",
        )
        for rank, (chunk, doc, score) in enumerate(rows, start=1)
    ]
