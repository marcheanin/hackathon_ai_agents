"""
Интеграционные тесты FastAPI routes с mock compiled_graph.
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.schemas.responses import (
    ArchitectureDraft,
    Component,
    ComponentType,
    DataFlow,
    GenerateResponse,
    ValidationResult,
)


def _mock_final_state(approved: bool = True) -> dict:
    components = [
        Component(
            id="api",
            name="API",
            type=ComponentType.API_GATEWAY,
            description="Handles requests",
            technology="FastAPI",
            dependencies=[],
        )
    ]
    data_flows: list[DataFlow] = []
    return {
        "user_request": "test request",
        "context": None,
        "retrieved_patterns": [],
        "selected_patterns": ["rag-agent"],
        "primary_pattern": "rag-agent",
        "pattern_reasoning": "Good fit",
        "components": components,
        "data_flows": data_flows,
        "mermaid_diagram": "C4Component\n    title Test",
        "yaml_spec": "title: Test\n",
        "validation_result": ValidationResult(
            approved=approved,
            score=0.85 if approved else 0.5,
            scores={"completeness": 0.9, "correctness": 0.8, "applicability": 0.85, "feasibility": 0.85},
            feedback="Looks good" if approved else "Missing components",
            issues=[],
        ),
        "feedback_history": [],
        "messages": [],
        "iteration_count": 1,
        "is_approved": approved,
        "error": None,
    }


@pytest.mark.asyncio
async def test_generate_success():
    mock_state = _mock_final_state(approved=True)

    with patch("app.api.v1.routes.compiled_graph") as mock_graph, \
         patch("app.rag.client.check_qdrant_health", return_value=True), \
         patch("app.rag.client.get_qdrant_client") as mock_client:

        mock_graph.ainvoke = AsyncMock(return_value=mock_state)
        mock_qdrant = AsyncMock()
        mock_qdrant.get_collections.return_value = AsyncMock(collections=[])
        mock_qdrant.create_collection = AsyncMock()
        mock_qdrant.create_payload_index = AsyncMock()
        mock_qdrant.close = AsyncMock()
        mock_client.return_value = mock_qdrant

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/generate",
                json={"user_request": "Нужен агент для мониторинга цен и отправки алертов"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["architecture"] is not None
    assert data["iterations"] == 1


@pytest.mark.asyncio
async def test_generate_max_retries():
    mock_state = _mock_final_state(approved=False)
    mock_state["iteration_count"] = 3

    with patch("app.api.v1.routes.compiled_graph") as mock_graph, \
         patch("app.rag.client.get_qdrant_client") as mock_client:

        mock_graph.ainvoke = AsyncMock(return_value=mock_state)
        mock_qdrant = AsyncMock()
        mock_qdrant.get_collections.return_value = AsyncMock(collections=[])
        mock_qdrant.create_collection = AsyncMock()
        mock_qdrant.create_payload_index = AsyncMock()
        mock_qdrant.close = AsyncMock()
        mock_client.return_value = mock_qdrant

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/generate",
                json={"user_request": "Нужен агент для мониторинга цен и отправки алертов"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "max_retries_exceeded"


@pytest.mark.asyncio
async def test_health_endpoint():
    with patch("app.api.v1.routes.check_qdrant_health", return_value=True), \
         patch("app.rag.client.get_qdrant_client") as mock_client:

        mock_qdrant = AsyncMock()
        mock_qdrant.get_collections.return_value = AsyncMock(collections=[])
        mock_qdrant.create_collection = AsyncMock()
        mock_qdrant.create_payload_index = AsyncMock()
        mock_qdrant.close = AsyncMock()
        mock_client.return_value = mock_qdrant

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["qdrant"] == "ok"


@pytest.mark.asyncio
async def test_generate_short_request_rejected():
    with patch("app.rag.client.get_qdrant_client") as mock_client:
        mock_qdrant = AsyncMock()
        mock_qdrant.get_collections.return_value = AsyncMock(collections=[])
        mock_qdrant.create_collection = AsyncMock()
        mock_qdrant.create_payload_index = AsyncMock()
        mock_qdrant.close = AsyncMock()
        mock_client.return_value = mock_qdrant

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/generate",
                json={"user_request": "short"},  # < 10 символов
            )

    assert response.status_code == 422
