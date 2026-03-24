"""МВАЛ — FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from mval.dependencies import close_resources, init_resources
from mval.gateway.router import router as gateway_router
from mval.logging.audit import configure_logging
from mval.policy.router import router as policy_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    await init_resources()
    yield
    await close_resources()


app = FastAPI(
    title="МВАЛ — Модуль валидации",
    description="Gatekeeper for Enterprise Multi-Agent System",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(gateway_router)
app.include_router(policy_router)
