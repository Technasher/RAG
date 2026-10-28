from __future__ import annotations

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.config import settings
from src.core.db.session import Base


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class DocumentStatus(str, enum.Enum):
    PENDING = "pending"        # загружен, но не проиндексирован
    INDEXED = "indexed"        # чанки созданы, эмбеддинги посчитаны
    FAILED = "failed"          # ошибка индексации
    ARCHIVED = "archived"      # устарел, можно не искать


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# --------------------------------------------------------------------------- #
# Document
# --------------------------------------------------------------------------- #
class Document(Base):
    """
    Логический документ: страница сайта, PDF, FAQ-файл, запись из БД.
    Содержит метаданные, но НЕ текст — текст живёт в Chunk.
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Идентификатор источника во внешней системе — чтобы не дублировать при переиндексации
    external_id: Mapped[str | None] = mapped_column(String(512), nullable=True)

    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # Произвольный «тип» источника: "web", "pdf", "faq", "schedule", "news"
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="web")

    # Метаданные (факультет, кафедра, теги, язык и т.п.)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, name="document_status"),
        nullable=False,
        default=DocumentStatus.PENDING,
        index=True,
    )

    # Хэш содержимого — чтобы не переиндексировать неизменившиеся документы
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Путь в storage, например "documents/1/schedule_2026.pdf"
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_mime: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Имя для скачивания (может отличаться от имени на диске)
    file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Chunk.chunk_index",
    )

    __table_args__ = (
        # Уникальность по (source_type, external_id) — только когда external_id задан
        UniqueConstraint(
            "source_type", "external_id", name="uq_documents_source_external"
        ),
        Index("ix_documents_meta_gin", "meta", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} type={self.source_type} title={self.title!r}>"


# --------------------------------------------------------------------------- #
# Chunk
# --------------------------------------------------------------------------- #
class Chunk(Base):
    """
    Фрагмент документа. Единица поиска и цитирования.
    Хранит эмбеддинг (для vector search) и tsvector (для BM25/FTS).
    """
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Вектор эмбеддинга. Размерность задаётся в config и ДОЛЖНА совпадать с моделью.
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dim), nullable=True
    )

    # Сгенерированная Postgres колонка для полнотекстового поиска.
    # 'russian'::regconfig — критично: иначе выражение не IMMUTABLE и нельзя GENERATED.
    content_tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            f"to_tsvector('{settings.fts_language}'::regconfig, coalesce(content, ''))",
            persisted=True,
        ),
        nullable=False,
    )

    # Доп. метаданные (страница PDF, заголовок раздела, позиция на странице)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_doc_index"),

        # HNSW-индекс для быстрого ANN-поиска по косинусу.
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),

        # GIN-индекс для FTS (BM25-подобное ранжирование через ts_rank_cd).
        Index(
            "ix_chunks_content_tsv_gin",
            "content_tsv",
            postgresql_using="gin",
        ),
    )

    def __repr__(self) -> str:
        return f"<Chunk id={self.id} doc={self.document_id} idx={self.chunk_index}>"


# --------------------------------------------------------------------------- #
# Conversation / Message — история диалога
# --------------------------------------------------------------------------- #
class Conversation(Base):
    """
    Один «разговор» — сквозной для всех каналов (telegram / web / api).
    session_id генерирует вызывающая сторона: 'tg:123456' или 'web:<uuid>'.
    """
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
        default=uuid.uuid4,
    )

    # Канал, из которого пришёл пользователь: 'telegram', 'web', 'api'
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="api")

    # Идентификатор пользователя в канале (для ограничения истории/прав)
    user_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.created_at",
    )

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} session={self.session_id} channel={self.channel}>"


class Message(Base):
    """Одно сообщение в диалоге (user / assistant / system)."""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped[MessageRole] = mapped_column(
        SAEnum(MessageRole, name="message_role"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Ссылки на источники (id чанков + url), которые использовала LLM.
    # Формат: [{"chunk_id": 42, "document_id": 3, "title": "...", "url": "...", "score": 0.81}]
    sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Служебное: сколько токенов потратили, какая модель, latency и т.п.
    usage: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message id={self.id} role={self.role} conv={self.conversation_id}>"