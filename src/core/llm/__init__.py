from src.core.config import Settings
from src.core.llm.base import LLMClient, LLMResponse
from src.core.llm.openai_client import OpenAICompatibleClient
from src.core.llm.ollama_client import OllamaClient


def build_llm(settings: Settings) -> LLMClient:
    """По конфигу выбираем провайдера. Используется в deps.get_llm()."""
    provider = (settings.llm_provider or "openai").lower()
    if provider in {"openai", "vllm", "openrouter"}:
        return OpenAICompatibleClient(settings)
    if provider == "ollama":
        return OllamaClient(settings)
    raise ValueError(f"Unknown LLM provider: {provider}")


__all__ = ["LLMClient", "LLMResponse", "build_llm"]