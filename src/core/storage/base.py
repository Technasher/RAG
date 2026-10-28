from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class StorageBackend(ABC):
    """Абстракция хранилища. Начните с LocalStorage, потом добавьте S3."""

    @abstractmethod
    async def save(self, key: str, source: Path | bytes) -> str:
        """Сохранить файл по ключу. Возвращает ключ."""

    @abstractmethod
    async def get_path(self, key: str) -> Path:
        """Локальный путь к файлу (для FSInputFile в Telegram)."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        ...


class LocalStorage(StorageBackend):
    """Простое локальное хранилище. Для MVP — идеально."""

    def __init__(self, base_dir: str = "data/storage") -> None:
        self._base = Path(base_dir).resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    async def save(self, key: str, source: Path | bytes) -> str:
        dst = self._base / key
        dst.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(source, bytes):
            dst.write_bytes(source)
        else:
            dst.write_bytes(source.read_bytes())
        return key

    async def get_path(self, key: str) -> Path:
        return self._base / key

    async def exists(self, key: str) -> bool:
        return (self._base / key).exists()

    async def delete(self, key: str) -> None:
        p = self._base / key
        if p.exists():
            p.unlink()