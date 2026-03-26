from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from analyst.gateway import router as gateway_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Явно включаем INFO для внутренних логов пайплайна (если root ещё не настроен).
    logging.getLogger("analyst.pipeline").setLevel(logging.INFO)
    yield


app = FastAPI(
    title="ИИ Аналитик — модуль модульной генерации агентов (MVP каркас)",
    description="Orchestrator и gateway для декомпозиции запроса клиента в банковский архитектурный план",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(gateway_router)

