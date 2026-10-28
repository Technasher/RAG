from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.api.deps import verify_admin, get_embedder
from src.core.api.schemas import IngestResponse, IngestUrlRequest
from src.core.config import settings
from src.core.db.session import get_db
from src.core.rag.ingest import ingest_url

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(verify_admin)],
)


@router.post("/ingest/url", response_model=IngestResponse)
async def ingest_single_url(
    payload: IngestUrlRequest,
    db: AsyncSession = Depends(get_db),
    embedder=Depends(get_embedder),
) -> IngestResponse:
    return IngestResponse(await ingest_url(
        db, url=payload.url, source_type=payload.source_type,
        meta=payload.meta, embedder=embedder, settings=settings,
    ))