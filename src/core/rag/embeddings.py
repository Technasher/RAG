from __future__ import annotations

from abc import ABC, abstractmethod

import httpx
from openai import AsyncOpenAI

from src.core.config import Settings
from src.core.rag.exceptions import RagError


class EmbeddingProvider(ABC):
    """Абстракция модели эмбеддингов."""

    dim: int
    name: str

    @abstractmethod
    async def embed_one(self, text: str) -> list[float]:
        ...

    @abstractmethod
    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        ...


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI-совместимый провайдер (OpenAI, vLLM, OpenRouter и т.п.)."""

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
        )
        self._model = settings.embedding_model
        self.dim = settings.embedding_dim
        self.name = self._model

    async def embed_one(self, text: str) -> list[float]:
        vectors = await self.embed_many([text])
        return vectors[0]

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=texts,
            )
        except Exception as exc:
            raise RagError(f"Embedding request failed: {exc}") from exc
        return [item.embedding for item in response.data]


def build_embedder(settings: Settings) -> EmbeddingProvider:
    """Фабрика: по конфигу выбираем провайдера."""
    provider = (settings.embedding_provider or "openai").lower()
    if provider == "openai":
        return OpenAIEmbeddingProvider(settings)
    raise ValueError(f"Unknown embedding provider: {provider}")