from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    """Результат вызова LLM. Usage — для метрик и биллинга."""
    text: str
    usage: dict = field(default_factory=dict)
    # usage = {"model": "...", "prompt_tokens": 120, "completion_tokens": 80}


class LLMClient(ABC):
    """Единый интерфейс для всех провайдеров."""

    model_name: str

    @abstractmethod
    async def generate(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> LLMResponse:
        """
        messages — в формате OpenAI Chat Completions:
        [{"role": "system"|"user"|"assistant", "content": "..."}]
        """

    async def health(self) -> bool:
        """Проверка доступности провайдера для /ready."""
        return True