# src/core/main.py
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.core.api.routes import api_router, health_router
from src.core.config import settings
from src.core.db.session import engine
from src.core.rag.exceptions import RagError

from fastapi.staticfiles import StaticFiles
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("API starting | llm=%s | embed=%s",
                settings.llm_model, settings.embedding_model)
    yield
    await engine.dispose()
    logger.info("API stopped")


app = FastAPI(
    title="RAG Assistant API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

widget_dir = Path("widget")
if widget_dir.exists():
    app.mount("/widget", StaticFiles(directory=widget_dir, html=True), name="widget")


@app.exception_handler(RagError)
async def rag_error_handler(request: Request, exc: RagError):
    """Ловит все необёрнутые RagError и превращает в 500 без стектрейса наружу."""
    logger.exception("Unhandled RagError on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal RAG error"},
    )


class NoCacheDevMiddleware(BaseHTTPMiddleware):
    """В dev не даём браузеру кэшировать статику виджета."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/widget"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


if settings.dev_mode:
    app.add_middleware(NoCacheDevMiddleware)
app.include_router(health_router)  # /health, /ready
app.include_router(api_router)  # /api/v1/chat, /api/v1/admin/*
