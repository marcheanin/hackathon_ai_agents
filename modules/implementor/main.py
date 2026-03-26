"""Модуль Реализации (заглушка).

Принимает одобренную архитектуру от Архитектора и (в будущем)
генерирует код по шаблонам из БД Шаблонов Кода.
Сейчас — placeholder, возвращающий статус stub.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="Модуль Реализации (заглушка)",
    description="Placeholder для будущей генерации кода по архитектуре",
    version="0.1.0",
)


class GenerateResponse(BaseModel):
    status: str
    message: str
    architecture_received: bool
    components_count: int


@app.post("/generate", response_model=GenerateResponse)
async def generate(body: dict[str, Any]) -> GenerateResponse:
    components = body.get("components", [])
    return GenerateResponse(
        status="stub",
        message="Модуль Реализации — заглушка. Генерация кода будет реализована позже.",
        architecture_received=bool(body),
        components_count=len(components),
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "implementor", "mode": "stub"}
