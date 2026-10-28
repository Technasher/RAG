from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.core.api.deps import get_chat_service
from src.core.api.schemas import ChatRequest, ChatResponse
from src.core.rag.exceptions import LLMError, RetrievalError
from src.core.services.chat_service import ChatService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    summary="Ответ на вопрос пользователя (RAG)",
)
async def chat(
    payload: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """
    Единственная точка входа для всех интерфейсов:
    - web-виджет     → POST /api/v1/chat
    - telegram-бот   → POST /api/v1/chat
    - внешние клиенты → тот же контракт

    Логика полностью в ChatService; роут только транслирует ошибки в HTTP.
    """
    try:
        return await service.handle(payload)

    except RetrievalError as exc:
        logger.exception("Retrieval failed for session=%s", payload.session_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search backend unavailable",
        ) from exc

    except LLMError as exc:
        logger.exception("LLM failed for session=%s", payload.session_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM provider error",
        ) from exc