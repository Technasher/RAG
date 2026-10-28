class RagError(Exception):
    """Базовое исключение для всего RAG-слоя."""


class RetrievalError(RagError):
    """Ошибка на этапе поиска (БД недоступна, битый индекс и т.п.)."""


class LLMError(RagError):
    """Ошибка при вызове языковой модели."""


class IngestionError(RagError):
    """Ошибка при индексации документа (парсинг, эмбеддинг)."""