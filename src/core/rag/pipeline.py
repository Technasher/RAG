from __future__ import annotations

from dataclasses import dataclass

from src.core.config import Settings
from src.core.llm.base import LLMClient
from src.core.rag.prompt import build_messages
from src.core.rag.retriever import HybridRetriever
from src.core.rag.vector_search import SearchHit


@dataclass
class RagAnswer:
    answer: str
    hits: list[SearchHit]
    usage: dict


async def answer_question(
    question: str,
    retriever: HybridRetriever,
    llm: LLMClient,
    settings: Settings,
    history: list[dict] | None = None,
    top_k: int | None = None,
) -> RagAnswer:
    # 1. Retrieve
    hits = await retriever.search(question, top_k=top_k)

    # 2. Prompt
    messages = build_messages(question, hits, history=history)

    # 3. Generate
    resp = await llm.generate(messages)
    return RagAnswer(
        answer=resp.text,
        hits=hits,
        usage={**resp.usage, "hits": len(hits)},
    )