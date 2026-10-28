from __future__ import annotations

import asyncio
import logging

from openai import AsyncOpenAI, APIError, APITimeoutError, RateLimitError

from src.core.config import Settings
from src.core.llm.base import LLMClient, LLMResponse
from src.core.rag.exceptions import LLMError

logger = logging.getLogger(__name__)


class OpenAICompatibleClient(LLMClient):
    """Работает с OpenAI, vLLM, OpenRouter, Together и любым OpenAI-совместимым API."""

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
            timeout=settings.llm_timeout_s,
            max_retries=0,  # свои ретраи — ниже
        )
        self._model = settings.llm_model
        self.model_name = self._model

    async def generate(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> LLMResponse:
        last_exc: Exception | None = None
        for attempt in range(1, 4):  # 3 попытки
            try:
                resp = await self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                choice = resp.choices[0].message.content or ""
                usage = {
                    "model": self._model,
                    "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                    "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
                }
                return LLMResponse(text=choice.strip(), usage=usage)

            except (RateLimitError, APITimeoutError, APIError) as exc:
                last_exc = exc
                backoff = 2 ** (attempt - 1)
                logger.warning(
                    "LLM attempt %d failed (%s), retry in %ds",
                    attempt, type(exc).__name__, backoff,
                )
                await asyncio.sleep(backoff)
            except Exception as exc:
                # не-ретраибельная ошибка (auth, битый запрос)
                raise LLMError(f"LLM request failed: {exc}") from exc

        raise LLMError(f"LLM failed after 3 attempts: {last_exc}")

    async def health(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False