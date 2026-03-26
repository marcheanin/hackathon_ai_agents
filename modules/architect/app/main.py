from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.routes import router
from app.config import settings
from app.rag.client import ensure_collection_exists, get_qdrant_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: проверяем/создаём коллекцию Qdrant
    client = get_qdrant_client()
    try:
        await ensure_collection_exists(client)
    finally:
        await client.close()
    yield
    # Shutdown: ничего дополнительного


app = FastAPI(
    title="ИИ Архитектор",
    description="Декомпозированный мульти-агент для генерации архитектуры AI-систем",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/")
async def root() -> dict:
    return {
        "service": "architecture-agent",
        "version": "0.1.0",
        "model": settings.llm_model,
        "docs": "/docs",
    }
