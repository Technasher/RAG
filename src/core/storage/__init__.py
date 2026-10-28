from functools import lru_cache

from src.core.config import settings
from src.core.storage.base import LocalStorage, StorageBackend


@lru_cache
def get_storage() -> StorageBackend:
    # позже: if settings.storage_backend == "s3": return S3Storage(...)
    return LocalStorage(settings.storage_dir)