from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.db.session import get_db
from src.core.rag.embeddings import build_embedder
from src.core.rag.retriever import HybridRetriever
from src.core.llm.base import LLMClient
from src.core.services.chat_service import ChatService


# --------------------------------------------------------------------------- #
# LLM — один на процесс (соединения/клиент переиспользуются)
# --------------------------------------------------------------------------- #
@lru_cache
def get_llm() -> LLMClient:
    """
    Возвращает синглтон LLM-клиента.
    Реальная фабрика (какой именно клиент) — в src/core/llm/__init__.py;
    здесь только кэш на процесс.
    """
    from src.core.llm import build_llm  # локальный импорт: избегаем циклов
    return build_llm(settings)


@lru_cache
def get_embedder():
    return build_embedder(settings)


# --------------------------------------------------------------------------- #
# Retriever — собирается на запрос, т.к. держит AsyncSession
# --------------------------------------------------------------------------- #
def get_retriever(
        db: Annotated[AsyncSession, Depends(get_db)],
) -> HybridRetriever:
    return HybridRetriever(db=db, embedder=get_embedder(), settings=settings)


# --------------------------------------------------------------------------- #
# ChatService — на запрос
# --------------------------------------------------------------------------- #
def get_chat_service(
        db: Annotated[AsyncSession, Depends(get_db)],
        llm: Annotated[LLMClient, Depends(get_llm)],
        retriever: Annotated[HybridRetriever, Depends(get_retriever)],
) -> ChatService:
    return ChatService(db=db, llm=llm, retriever=retriever, settings=settings)


# --------------------------------------------------------------------------- #
# Admin-auth
# --------------------------------------------------------------------------- #
async def verify_admin(
        x_admin_key: Annotated[str | None, Header(alias="X-Admin-Key")] = None,
) -> None:
    """
    Простая защита админ-эндпоинтов по статическому ключу.
    В проде замените на JWT/OAuth2 — но принцип тот же: это зависимость,
    которую можно повесить на любой роут.
    """
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key",
        )



