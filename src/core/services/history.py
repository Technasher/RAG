from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.db.models import Conversation, Message, MessageRole


async def get_or_create_conversation(
    db: AsyncSession,
    session_id: uuid.UUID | None,
    channel: str,
    user_ref: str | None,
) -> tuple[Conversation, uuid.UUID]:
    """
    Возвращает (conversation, session_id).
    Если session_id не передан — создаём новую беседу и генерируем UUID.
    """
    if session_id is not None:
        stmt = select(Conversation).where(Conversation.session_id == session_id)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return existing, existing.session_id

    conversation = Conversation(
        session_id=session_id or uuid.uuid4(),
        channel=channel,
        user_ref=user_ref,
        meta={},
    )
    db.add(conversation)
    await db.flush()
    return conversation, conversation.session_id


async def load_history(
    db: AsyncSession,
    conversation_id: int,
    limit: int = 10,
) -> list[dict]:
    """
    Возвращает последние N сообщений в формате OpenAI Chat Completions.
    Берём последние limit, потом разворачиваем в хронологический порядок.
    """
    stmt = (
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.role.in_([MessageRole.USER, MessageRole.ASSISTANT]),
        )
        .order_by(Message.id.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    rows.reverse()

    return [
        {
            "role": m.role.value,
            # обрезаем длинные ответы ассистента: они уже не нужны в полном объёме
            "content": m.content if m.role == MessageRole.USER else m.content[:1500],
        }
        for m in rows
    ]


async def append_message(
    db: AsyncSession,
    conversation: Conversation,
    role: MessageRole,
    content: str,
    *,
    sources: list | None = None,
    usage: dict | None = None,
) -> Message:
    msg = Message(
        conversation_id=conversation.id,
        role=role,
        content=content,
        sources=sources,
        usage=usage or {},
    )
    db.add(msg)
    await db.flush()  # id нужен для ответа клиенту
    return msg