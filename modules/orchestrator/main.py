"""Оркестратор — связующий сервис полного пайплайна генерации агентов.

Пайплайн:
  Клиент → Аналитик → МВАЛ (REQUEST) → Архитектор → МВАЛ (ARCHITECTURE) → Реализация (заглушка)
"""
from __future__ import annotations

import os
import uuid
from typing import Any

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

ANALYST_URL = os.getenv("ANALYST_URL", "http://analyst:8010")
MVAL_URL = os.getenv("MVAL_URL", "http://mval:8020")
ARCHITECT_URL = os.getenv("ARCHITECT_URL", "http://architect:8030")
IMPLEMENTOR_URL = os.getenv("IMPLEMENTOR_URL", "http://implementor:8040")

TIMEOUT = httpx.Timeout(600.0, connect=10.0)

app = FastAPI(
    title="Оркестратор — Система Генерации Агентов",
    description="Координирует полный пайплайн: Аналитик → МВАЛ → Архитектор → МВАЛ → Реализация",
    version="0.1.0",
)


class PipelineRequest(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    message: str = Field(..., min_length=5)


class PipelineResponse(BaseModel):
    stage: str
    status: str
    data: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "orchestrator"}


@app.post("/pipeline", response_model=PipelineResponse)
async def run_pipeline(req: PipelineRequest) -> PipelineResponse:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # 1. Аналитик: декомпозиция запроса
        analyst_resp = await client.post(
            f"{ANALYST_URL}/analyze",
            json={"session_id": req.session_id, "message": req.message},
        )
        analyst_resp.raise_for_status()
        analyst_data = analyst_resp.json()

        kind = analyst_data.get("kind")

        # Если аналитик требует уточнения — возвращаем вопросы
        if kind == "clarification":
            return PipelineResponse(
                stage="analyst",
                status="needs_clarification",
                data=analyst_data,
            )

        if kind == "redirect":
            return PipelineResponse(
                stage="analyst",
                status="redirect",
                data=analyst_data,
            )

        if kind == "redirect_choice":
            return PipelineResponse(
                stage="analyst",
                status="redirect_choice",
                data=analyst_data,
            )

        if kind != "final":
            return PipelineResponse(
                stage="analyst",
                status="unexpected",
                data=analyst_data,
            )

        concretized = analyst_data.get("concretized_request", {})

        # 2. МВАЛ: валидация запроса
        artifact = concretized.get("concretized_request", concretized)
        mval_req_resp = await client.post(
            f"{MVAL_URL}/validate",
            json={
                "phase": "REQUEST",
                "source_module": "analyst",
                "target_module": "architecture",
                "artifact": artifact,
                "metadata": {"session_id": req.session_id},
            },
        )
        mval_req_resp.raise_for_status()
        mval_req_data = mval_req_resp.json()

        if mval_req_data.get("verdict") == "FAIL":
            return PipelineResponse(
                stage="mval_request",
                status="validation_failed",
                data=mval_req_data,
            )

        # 3. Архитектор: генерация архитектуры
        arch_resp = await client.post(
            f"{ARCHITECT_URL}/api/v1/generate",
            json={
                "user_request": req.message,
                "context": {
                    "input_data": concretized,
                    "system_instructions": "Ты — ИИ Архитектор. Используй данные от ИИ Аналитика.",
                },
            },
        )
        arch_resp.raise_for_status()
        arch_data = arch_resp.json()

        if arch_data.get("status") != "success":
            return PipelineResponse(
                stage="architect",
                status=arch_data.get("status", "error"),
                data=arch_data,
            )

        # 4. МВАЛ: валидация архитектуры
        arch_artifact = arch_data.get("architecture", {})
        mval_arch_resp = await client.post(
            f"{MVAL_URL}/validate",
            json={
                "phase": "ARCHITECTURE",
                "source_module": "architecture",
                "target_module": "implementation",
                "artifact": arch_artifact,
                "metadata": {"session_id": req.session_id},
            },
        )
        mval_arch_resp.raise_for_status()
        mval_arch_data = mval_arch_resp.json()

        if mval_arch_data.get("verdict") == "FAIL":
            return PipelineResponse(
                stage="mval_architecture",
                status="validation_failed",
                data={
                    "architecture": arch_data,
                    "validation": mval_arch_data,
                },
            )

        # 5. Реализация (заглушка)
        impl_resp = await client.post(
            f"{IMPLEMENTOR_URL}/generate",
            json=arch_artifact,
        )
        impl_resp.raise_for_status()
        impl_data = impl_resp.json()

        return PipelineResponse(
            stage="complete",
            status="success",
            data={
                "analyst": {"concretized_request": concretized},
                "mval_request_validation": mval_req_data,
                "architecture": arch_data,
                "mval_architecture_validation": mval_arch_data,
                "implementation": impl_data,
            },
        )


@app.websocket("/ws/pipeline/{session_id}")
async def ws_pipeline(websocket: WebSocket, session_id: str):
    """WebSocket для многошагового диалога (уточнения аналитика)."""
    await websocket.accept()

    try:
        while True:
            text = await websocket.receive_text()

            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                # Шаг аналитика
                analyst_resp = await client.post(
                    f"{ANALYST_URL}/analyze",
                    json={"session_id": session_id, "message": text},
                )
                analyst_resp.raise_for_status()
                analyst_data = analyst_resp.json()
                kind = analyst_data.get("kind")

                if kind == "clarification":
                    await websocket.send_json({
                        "stage": "analyst",
                        "status": "needs_clarification",
                        "data": analyst_data,
                    })
                    continue

                if kind == "redirect_choice":
                    await websocket.send_json({
                        "stage": "analyst",
                        "status": "redirect_choice",
                        "data": analyst_data,
                    })
                    continue

                if kind == "redirect":
                    await websocket.send_json({
                        "stage": "analyst",
                        "status": "redirect",
                        "data": analyst_data,
                    })
                    break

                if kind != "final":
                    await websocket.send_json({
                        "stage": "analyst",
                        "status": "unexpected",
                        "data": analyst_data,
                    })
                    continue

                # Финальный запрос — запускаем остальной пайплайн
                concretized = analyst_data.get("concretized_request", {})
                artifact = concretized.get("concretized_request", concretized)

                await websocket.send_json({
                    "stage": "analyst",
                    "status": "finalized",
                    "data": {"concretized_request": concretized},
                })

                # МВАЛ REQUEST
                mval_resp = await client.post(
                    f"{MVAL_URL}/validate",
                    json={
                        "phase": "REQUEST",
                        "source_module": "analyst",
                        "target_module": "architecture",
                        "artifact": artifact,
                        "metadata": {"session_id": session_id},
                    },
                )
                mval_resp.raise_for_status()
                mval_data = mval_resp.json()

                if mval_data.get("verdict") == "FAIL":
                    await websocket.send_json({
                        "stage": "mval_request",
                        "status": "validation_failed",
                        "data": mval_data,
                    })
                    break

                await websocket.send_json({
                    "stage": "mval_request",
                    "status": "passed",
                    "data": mval_data,
                })

                # Архитектор
                arch_resp = await client.post(
                    f"{ARCHITECT_URL}/api/v1/generate",
                    json={
                        "user_request": text,
                        "context": {
                            "input_data": concretized,
                            "system_instructions": "Ты — ИИ Архитектор.",
                        },
                    },
                )
                arch_resp.raise_for_status()
                arch_data = arch_resp.json()

                await websocket.send_json({
                    "stage": "architect",
                    "status": arch_data.get("status", "unknown"),
                    "data": arch_data,
                })

                if arch_data.get("status") != "success":
                    break

                # МВАЛ ARCHITECTURE
                arch_artifact = arch_data.get("architecture", {})
                mval_arch_resp = await client.post(
                    f"{MVAL_URL}/validate",
                    json={
                        "phase": "ARCHITECTURE",
                        "source_module": "architecture",
                        "target_module": "implementation",
                        "artifact": arch_artifact,
                        "metadata": {"session_id": session_id},
                    },
                )
                mval_arch_resp.raise_for_status()
                mval_arch_data = mval_arch_resp.json()

                await websocket.send_json({
                    "stage": "mval_architecture",
                    "status": "passed" if mval_arch_data.get("verdict") != "FAIL" else "validation_failed",
                    "data": mval_arch_data,
                })

                # Реализация
                impl_resp = await client.post(
                    f"{IMPLEMENTOR_URL}/generate",
                    json=arch_artifact,
                )
                impl_resp.raise_for_status()
                impl_data = impl_resp.json()

                await websocket.send_json({
                    "stage": "complete",
                    "status": "success",
                    "data": impl_data,
                })
                break

    except WebSocketDisconnect:
        pass
