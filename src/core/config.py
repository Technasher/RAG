# src/core/config.py
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- DB ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/rag"
    sql_echo: bool = False

    # --- Storage ---
    raw_dir: str = "data/raw"
    storage_dir: str = "data/storage"

    # --- Embeddings ---
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # --- Chunking / Retrieval ---
    chunk_size: int = 800
    chunk_overlap: int = 120
    top_k_vector: int = 20
    top_k_bm25: int = 20
    top_k_final: int = 6
    rrf_k: int = 60
    fts_language: str = "russian"

    # --- LLM ---
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_s: float = 30.0
    llm_temperature: float = 0.2
    llm_max_tokens: int = 800
    openai_api_key: str = ""
    openai_base_url: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # --- HTTP ---
    cors_origins: list[str] = ["http://localhost:5173"]
    admin_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()