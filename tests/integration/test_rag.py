# tests/integration/test_rag.py
import pytest
from src.core.config import settings
from src.core.db import AsyncSessionLocal
from src.core.rag.embeddings import build_embedder
from src.core.rag.ingest import ingest_text
from src.core.rag.retriever import HybridRetriever


@pytest.mark.asyncio
async def test_hybrid_retrieval():
    embedder = build_embedder(settings)
    async with AsyncSessionLocal() as db:
        await ingest_text(
            db,
            title="Расписание матана",
            text="Консультация по математическому анализу "
                 "состоится в среду в 15:00 в аудитории 312.",
            source_type="schedule",
            external_id="math-consult",
            embedder=embedder,
            settings=settings,
        )

        retriever = HybridRetriever(db=db, embedder=embedder, settings=settings)
        hits = await retriever.search("когда консультация по матанализу?", top_k=3)

        assert hits
        assert "среду" in hits[0].content
        