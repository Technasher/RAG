from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db.models import Chunk, Document
from src.core.rag.exceptions import RetrievalError


@dataclass
class SearchHit:
    """Единый формат результата поиска (для обоих видов)."""
    chunk_id: int
    document_id: int
    content: str
    title: str
    url: str | None
    rank: int
    raw_score: float
    source: str  # "vector" | "bm25"


async def vector_search(
    db: AsyncSession,
    query_embedding: list[float],
    limit: int = 20,
    min_similarity: float = 0.25,
) -> list[SearchHit]:
    """
    Возвращает top-N чанков по косинусной близости.
    1 - cosine_distance = similarity (1 = идентичны).
    """
    try:
        distance = Chunk.embedding.cosine_distance(query_embedding).label("distance")
        stmt = (
            select(Chunk, Document, distance)
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.embedding.is_not(None))
            .where(Document.status == "INDEXED")  # ищем только по проиндексированным
            .order_by(distance)
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()
    except Exception as exc:
        raise RetrievalError(f"Vector search failed: {exc}") from exc

    hits: list[SearchHit] = []
    for rank, (chunk, doc, dist) in enumerate(rows, start=1):
        similarity = 1.0 - float(dist)
        if similarity < min_similarity:
            continue
        hits.append(
            SearchHit(
                chunk_id=chunk.id,
                document_id=doc.id,
                content=chunk.content,
                title=doc.title,
                url=doc.source_url,
                rank=rank,
                raw_score=similarity,
                source="vector",
            )
        )
    return hits