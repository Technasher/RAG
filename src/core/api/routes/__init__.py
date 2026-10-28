from fastapi import APIRouter

from src.core.api.routes import admin, chat, health, files

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(chat.router)
api_router.include_router(admin.router)
api_router.include_router(files.router)

# health подключаем БЕЗ /api/v1 — так принято у балансировщиков и k8s
health_router = health.router

__all__ = ["api_router", "health_router"]