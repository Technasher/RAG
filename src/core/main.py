# src/core/main.py
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.api.routes import api_router, health_router
from src.core.config import settings
from src.core.db.session import engine
from src.core.rag.exceptions import RagError

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


@app.exception_handler(RagError)
async def rag_error_handler(request: Request, exc: RagError):
    """Ловит все необёрнутые RagError и превращает в 500 без стектрейса наружу."""
    logger.exception("Unhandled RagError on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal RAG error"},
    )


app.include_router(health_router)   # /health, /ready
app.include_router(api_router)      # /api/v1/chat, /api/v1/admin/*
