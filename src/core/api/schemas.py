from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


Channel = Literal["web", "telegram", "api"]


class QuickReply(BaseModel):
    label: str           # текст на кнопке ("📅 Расписание")
    intent: str          # что отправить в следующий раз


class Attachment(BaseModel):
    """Файл, прикреплённый к ответу бота."""
    document_id: int
    filename: str                # для отображения ("Расписание_2026.pdf")
    mime_type: str               # "application/pdf"
    size: int                    # байты
    url: str                     # "/api/v1/files/1" — относительный URL, бот сам разберётся


# --------------------------------------------------------------------------- #
# Chat
# --------------------------------------------------------------------------- #
class ChatRequest(BaseModel):
    """Запрос от любого интерфейса (web / telegram / api)."""
    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1, max_length=4000)
    intent: str | None = Field(default=None, max_length=64)
    # Если клиент ещё не имеет сессии — передаёт null, сервер сгенерирует UUID
    # и вернёт в ответе. Клиент сохраняет его (localStorage / chat_id в боте).
    session_id: UUID | None = None

    channel: Channel = "api"
    user_ref: str | None = Field(
        default=None,
        max_length=128,
        description="Идентификатор пользователя в канале (tg chat_id, web user_id)",
    )

    # Переопределение параметров поиска на один запрос (для отладки/тестов)
    top_k: int | None = Field(default=None, ge=1, le=50)


class Source(BaseModel):
    """Ссылка на фрагмент, который LLM использовала при ответе."""
    chunk_id: int
    document_id: int
    title: str
    url: str | None = None
    score: float = Field(..., description="Итоговая RRF-оценка (нормализованная)")
    snippet: str | None = Field(default=None, max_length=500)


class ChatResponse(BaseModel):
    session_id: UUID = Field(..., description="Клиент обязан сохранить и переиспользовать")
    message_id: int = Field(..., description="ID сохранённого сообщения assistant")
    answer: str
    sources: list[Source] = Field(default_factory=list)
    attachments: list[Attachment] = Field(default_factory=list)
    quick_replies: list[QuickReply] = Field(default_factory=list)
    usage: dict = Field(
        default_factory=dict,
        description="model, prompt_tokens, completion_tokens, latency_ms",
    )


# --------------------------------------------------------------------------- #
# Admin
# --------------------------------------------------------------------------- #
class IngestUrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(..., max_length=2048)
    source_type: str = Field(default="web", max_length=64)
    meta: dict = Field(default_factory=dict)


class IngestResponse(BaseModel):
    document_id: int
    status: Literal["created", "updated", "skipped"]
    chunks_created: int


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #
class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


class ReadyResponse(BaseModel):
    status: Literal["ready", "degraded"]
    db: bool
    llm: bool