from __future__ import annotations

from src.core.rag.vector_search import SearchHit

SYSTEM_PROMPT = """Ты — официальный помощник университета.
Отвечай ТОЛЬКО на основе предоставленного контекста.
Если в контексте нет ответа — честно скажи: «Я не нашёл этой информации в базе знаний».
Не выдумывай факты, даты, имена и номера.
Отвечай кратко, по-русски, без воды.
Если уместно — ссылайся на источники в формате [1], [2]."""


def build_context(hits: list[SearchHit], max_chars: int = 6000) -> str:
    """Собирает контекст с нумерованными источниками."""
    parts: list[str] = []
    total = 0
    for i, hit in enumerate(hits, start=1):
        block = f"[{i}] {hit.title}\n{hit.content}"
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)
    return "\n\n".join(parts)


def build_messages(
    question: str,
    hits: list[SearchHit],
    history: list[dict] | None = None,
) -> list[dict]:
    """Возвращает messages в формате OpenAI Chat Completions."""
    context = build_context(hits)
    user_content = (
        f"Контекст:\n{context}\n\n"
        f"Вопрос пользователя: {question}"
    )
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_content})
    return messages