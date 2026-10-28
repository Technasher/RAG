from __future__ import annotations

import httpx

from src.core.config import Settings
from src.core.llm.base import LLMClient, LLMResponse
from src.core.rag.exceptions import LLMError


class OllamaClient(LLMClient):
    """Ollama /chat endpoint. Удобно для локальной разработки без затрат на API."""

    def __init__(self, settings: Settings) -> None:
        self._base = settings.ollama_base_url.rstrip("/")
        self._model = settings.llm_model
        self._timeout = settings.llm_timeout_s
        self.model_name = f"ollama:{self._model}"

    async def generate(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> LLMResponse:
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                r = await client.post(f"{self._base}/api/chat", json=payload)
                r.raise_for_status()
                data = r.json()
        except Exception as exc:
            raise LLMError(f"Ollama request failed: {exc}") from exc

        return LLMResponse(
            text=data["message"]["content"].strip(),
            usage={
                "model": self.model_name,
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
        )