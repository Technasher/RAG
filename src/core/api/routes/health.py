from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.api.schemas import HealthResponse, ReadyResponse
from src.core.db.session import get_db

router = APIRouter(tags=["health"])

APP_VERSION = "0.1.0"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness-проба: процесс жив. Не проверяет зависимости."""
    return HealthResponse(status="ok", version=APP_VERSION)


@router.get("/ready", response_model=ReadyResponse)
async def ready(db: AsyncSession = Depends(get_db)) -> ReadyResponse:
    """
    Readiness-проба: можно ли принимать трафик.
    Проверяет БД (обязательно). Проверку LLM можно добавить с кэшем на 30 с.
    """
    db_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    llm_ok = True  # TODO: реальная проверка через ping/embedding
    overall = "ready" if (db_ok and llm_ok) else "degraded"

    return ReadyResponse(status=overall, db=db_ok, llm=llm_ok)