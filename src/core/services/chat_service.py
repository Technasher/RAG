"""
Оркестратор запросов к чат-боту.

Два маршрута:
  1. Intent route (вариант C) — пользователь нажал кнопку, известен intent.
     Детерминированный ответ + возможно прикреплённый файл. Без LLM.
  2. RAG route (вариант A) — свободный текст. Гибридный поиск + LLM +
     правило _should_attach для прикрепления файлов.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.api.schemas import (
    Attachment,
    ChatRequest,
    ChatResponse,
    QuickReply,
    Source,
)
from src.core.config import Settings
from src.core.db.models import Document, MessageRole
from src.core.llm.base import LLMClient
from src.core.rag.prompt import build_messages
from src.core.rag.retriever import HybridRetriever
from src.core.services import history
from src.core.services.intents import INTENTS, STARTER_INTENTS, Intent
from src.shared.text import truncate

logger = logging.getLogger(__name__)


# Слова-триггеры, по которым RAG прикрепляет файл даже без явного «покажи»
_FILE_KEYWORDS = {"файл", "покажи", "пришли", "скинь", "pdf", "скачать", "документ"}

# source_type → intent, используется для quick_replies в RAG-маршруте
_SOURCE_TO_INTENT: dict[str, str] = {
    "schedule": "show_schedule",
    "pdf_schedule": "show_schedule",
    "admission": "admission",
    "faq": "contacts",
}

# source_type, для которых файл прикрепляется автоматически
_ATTACHABLE_SOURCE_TYPES = {"schedule", "pdf_schedule", "document"}


class ChatService:
    def __init__(
        self,
        db: AsyncSession,
        llm: LLMClient,
        retriever: HybridRetriever,
        settings: Settings,
    ) -> None:
        self._db = db
        self._llm = llm
        self._retriever = retriever
        self._settings = settings

    # ------------------------------------------------------------------ #
    # Точка входа
    # ------------------------------------------------------------------ #
    async def handle(self, req: ChatRequest) -> ChatResponse:
        t0 = time.monotonic()

        # 1. Беседа: найти или создать (общая для всех каналов)
        conversation, session_id = await history.get_or_create_conversation(
            self._db,
            session_id=req.session_id,
            channel=req.channel,
            user_ref=req.user_ref,
        )

        # 2. Роутинг
        if req.intent:
            intent = INTENTS.get(req.intent)
            if intent is not None:
                return await self._handle_intent(
                    conversation, session_id, intent, t0
                )
            # Неизвестный intent: если есть message — пробуем RAG,
            # иначе показываем стартовое меню
            if req.message:
                logger.info(
                    "Unknown intent '%s', falling back to RAG", req.intent
                )
                return await self._handle_rag(
                    conversation, session_id,
                    message=req.message, top_k=req.top_k, t0=t0,
                )
            logger.warning("Unknown intent '%s' without message", req.intent)
            return await self._handle_unknown_intent(
                conversation, session_id, req.intent, t0
            )

        # Только message
        if not req.message:
            # Схема не должна пропустить, но на всякий случай
            raise ValueError("ChatRequest must contain 'message' or 'intent'")

        return await self._handle_rag(
            conversation, session_id,
            message=req.message, top_k=req.top_k, t0=t0,
        )

    # ------------------------------------------------------------------ #
    # INTENT ROUTE (вариант C)
    # ------------------------------------------------------------------ #
    async def _handle_intent(
        self,
        conversation,
        session_id,
        intent: Intent,
        t0: float,
    ) -> ChatResponse:
        """Детерминированный ответ по нажатой кнопке. Без LLM."""
        # 1. Сохраняем «нажатие кнопки» в историю
        await history.append_message(
            self._db, conversation, MessageRole.USER, intent.label
        )

        # 2. Прикрепляем файл, если задан в intent
        attachments = await self._resolve_intent_attachment(intent)

        # 3. Считаем метрики и сохраняем ответ
        latency_ms = int((time.monotonic() - t0) * 1000)
        usage = {
            "route": "intent",
            "intent": intent.key,
            "latency_ms": latency_ms,
            "attachments": len(attachments),
        }

        assistant_msg = await history.append_message(
            self._db,
            conversation,
            MessageRole.ASSISTANT,
            intent.answer,
            sources=[{"intent": intent.key}],
            usage=usage,
        )
        await self._db.commit()

        return ChatResponse(
            session_id=session_id,
            message_id=assistant_msg.id,
            answer=intent.answer,
            attachments=attachments,
            quick_replies=self._build_quick_replies(intent.related),
            usage=usage,
        )

    async def _resolve_intent_attachment(self, intent: Intent) -> list[Attachment]:
        """Ищет документ по external_id и превращает в Attachment."""
        if not intent.document_external_id:
            return []

        stmt = select(Document).where(
            Document.external_id == intent.document_external_id,
            Document.file_path.is_not(None),
        )
        doc = (await self._db.execute(stmt)).scalar_one_or_none()

        if doc is None:
            logger.warning(
                "Intent '%s' references missing document external_id='%s'",
                intent.key,
                intent.document_external_id,
            )
            return []

        return [self._make_attachment(doc)]

    async def _handle_unknown_intent(
        self,
        conversation,
        session_id,
        intent_key: str,
        t0: float,
    ) -> ChatResponse:
        """Неизвестный intent без message: показываем меню."""
        answer = (
            f"Не понял команду «{intent_key}». "
            "Выберите, что вас интересует:"
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        usage = {"route": "unknown_intent", "intent": intent_key, "latency_ms": latency_ms}

        await history.append_message(
            self._db, conversation, MessageRole.USER, intent_key
        )
        assistant_msg = await history.append_message(
            self._db, conversation, MessageRole.ASSISTANT, answer, usage=usage,
        )
        await self._db.commit()

        return ChatResponse(
            session_id=session_id,
            message_id=assistant_msg.id,
            answer=answer,
            quick_replies=self._build_quick_replies(STARTER_INTENTS),
            usage=usage,
        )

    # ------------------------------------------------------------------ #
    # RAG ROUTE (вариант A)
    # ------------------------------------------------------------------ #
    async def _handle_rag(
        self,
        conversation,
        session_id,
        message: str,
        top_k: int | None,
        t0: float,
    ) -> ChatResponse:
        """Свободный текст: гибридный поиск + LLM + правило прикрепления."""
        # 1. История ДО текущего сообщения
        chat_history = await history.load_history(
            self._db, conversation.id, limit=10
        )

        # 2. Сохраняем вопрос пользователя (до LLM — если LLM упадёт,
        #    вопрос всё равно останется в истории)
        await history.append_message(
            self._db, conversation, MessageRole.USER, message
        )

        # 3. Гибридный поиск
        hits = await self._retriever.search(
            message,
            top_k=top_k or self._settings.top_k_final,
        )

        # 4. Промпт + LLM
        messages = build_messages(message, hits, history=chat_history)
        llm_resp = await self._llm.generate(
            messages,
            temperature=self._settings.llm_temperature,
            max_tokens=self._settings.llm_max_tokens,
        )

        # 5. Вложения по правилу
        attachments = await self._resolve_rag_attachments(hits, message)

        # 6. Quick replies из source_type найденных документов
        suggested_intents = await self._suggest_intents(hits)

        # 7. Метрики, сохранение, ответ
        latency_ms = int((time.monotonic() - t0) * 1000)
        usage = {
            **llm_resp.usage,
            "route": "rag",
            "hits": len(hits),
            "attachments": len(attachments),
            "latency_ms": latency_ms,
        }

        sources_payload = [
            {
                "chunk_id": h.chunk_id,
                "document_id": h.document_id,
                "title": h.title,
                "url": h.url,
                "score": round(h.raw_score, 4),
            }
            for h in hits
        ]

        assistant_msg = await history.append_message(
            self._db,
            conversation,
            MessageRole.ASSISTANT,
            llm_resp.text,
            sources=sources_payload,
            usage=usage,
        )
        await self._db.commit()

        return ChatResponse(
            session_id=session_id,
            message_id=assistant_msg.id,
            answer=llm_resp.text,
            sources=[
                Source(
                    chunk_id=s["chunk_id"],
                    document_id=s["document_id"],
                    title=s["title"],
                    url=s["url"],
                    score=s["score"],
                    snippet=truncate(
                        self._hit_snippet(hits, s["chunk_id"]), 300
                    ),
                )
                for s in sources_payload
            ],
            attachments=attachments,
            quick_replies=self._build_quick_replies(suggested_intents),
            usage=usage,
        )

    async def _resolve_rag_attachments(
        self, hits: list, message: str
    ) -> list[Attachment]:
        """Прикрепляет не более одного файла, если сработало правило."""
        seen_docs: set[int] = set()
        for hit in hits:
            if hit.document_id in seen_docs:
                continue
            seen_docs.add(hit.document_id)

            doc = await self._db.get(Document, hit.document_id)
            if not doc or not doc.file_path:
                continue
            if not self._should_attach(doc, message):
                continue

            return [self._make_attachment(doc)]

        return []

    def _should_attach(self, doc: Document, message: str) -> bool:
        """
        Три независимых условия:
          1. meta.always_attach=True (ставится ingest_pdf для сканов).
          2. Пользователь явно просит файл.
          3. Тип документа — тот, что обычно отдают файлом.
        """
        if doc.meta and doc.meta.get("always_attach"):
            return True

        msg_lower = (message or "").lower()
        if any(kw in msg_lower for kw in _FILE_KEYWORDS):
            return True

        return doc.source_type in _ATTACHABLE_SOURCE_TYPES

    async def _suggest_intents(self, hits: list) -> list[str]:
        """
        Из source_type найденных документов формирует список связанных intent'ов.
        Если ничего не нашли — стартовое меню.
        """
        if not hits:
            return list(STARTER_INTENTS)

        doc_ids = list({h.document_id for h in hits[:5]})
        if not doc_ids:
            return list(STARTER_INTENTS)

        stmt = select(Document.source_type).where(Document.id.in_(doc_ids))
        source_types = (await self._db.execute(stmt)).scalars().all()

        intents: list[str] = []
        for st in source_types:
            mapped = _SOURCE_TO_INTENT.get(st)
            if mapped and mapped not in intents:
                intents.append(mapped)

        return intents[:3] if intents else list(STARTER_INTENTS)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _build_quick_replies(self, intent_keys: list[str]) -> list[QuickReply]:
        result: list[QuickReply] = []
        for key in intent_keys:
            intent = INTENTS.get(key)
            if intent is None:
                continue
            result.append(QuickReply(label=intent.label, intent=intent.key))
        return result

    @staticmethod
    def _make_attachment(doc: Document) -> Attachment:
        return Attachment(
            document_id=doc.id,
            filename=doc.file_name or Path(doc.file_path).name,
            mime_type=doc.file_mime or "application/octet-stream",
            size=doc.file_size or 0,
            url=f"/api/v1/files/{doc.id}",
        )

    @staticmethod
    def _hit_snippet(hits: list, chunk_id: int) -> str:
        for h in hits:
            if h.chunk_id == chunk_id:
                return h.content
        return ""