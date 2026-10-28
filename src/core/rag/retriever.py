from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.rag.bm25_search import bm25_search
from src.core.rag.embeddings import EmbeddingProvider
from src.core.rag.rrf import reciprocal_rank_fusion
from src.core.rag.vector_search import SearchHit, vector_search


class HybridRetriever:
    def __init__(
        self,
        db: AsyncSession,
        embedder: EmbeddingProvider,
        settings: Settings,
    ) -> None:
        self._db = db
        self._embedder = embedder
        self._settings = settings

    async def search(
        self,
        query: str,
        top_k: int | None = None,
    ) -> list[SearchHit]:
        top_k = top_k or self._settings.top_k_final

        # 1. Эмбеддинг запроса
        query_embedding = await self._embedder.embed_one(query)

        # 2. Оба поиска параллельно (они не зависят друг от друга)
        vector_task = vector_search(
            db=self._db,
            query_embedding=query_embedding,
            limit=self._settings.top_k_vector,
        )
        bm25_task = bm25_search(
            db=self._db,
            query=query,
            limit=self._settings.top_k_bm25,
        )

        vector_hits, bm25_hits = await asyncio.gather(vector_task, bm25_task)

        # 3. Слияние через RRF
        return reciprocal_rank_fusion(
            [vector_hits, bm25_hits],
            k=self._settings.rrf_k,
            top_k=top_k,
        )
    