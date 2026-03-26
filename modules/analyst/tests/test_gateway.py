from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from analyst.main import app


def test_health_and_rest_analyze_smoke() -> None:
    client = TestClient(app)

    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    # REST анализатор — просто проверяем, что endpoint существует и возвращает структуру
    r2 = client.post(
        "/analyze",
        json={"session_id": "sess_ws_rest", "message": "Нужен портал тикетов банка-клиента с SMS-уведомлениями"},
    )
    assert r2.status_code == 200
    assert "kind" in r2.json()


def test_websocket_returns_kind_response() -> None:
    client = TestClient(app)
    with client.websocket_connect("/ws/sess_ws_1") as ws:
        ws.send_text(
            "Нужен портал тикетов для банков-клиентов, до 100к обращений в месяц, с подтверждением по SMS"
        )
        data = ws.receive_json()
        assert "kind" in data

