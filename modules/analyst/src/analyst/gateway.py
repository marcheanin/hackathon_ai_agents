from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from analyst.orchestrator import AnalystOrchestrator
from analyst.config import MVAL_BASE_URL, MVAL_VALIDATE_PATH
from analyst.observability import pipeline_log
from analyst.session import SessionManager

router = APIRouter()

_LOG_DIR = Path(os.getenv("LLM_LOG_DIR", "/tmp/agent_logs"))
_LOG_DIR.mkdir(parents=True, exist_ok=True)


def _log_analyst(session_id: str, message: str, result: dict) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(_LOG_DIR / "analyst.log", "a", encoding="utf-8") as f:
        f.write(f"\n{'='*80}\n[{ts}] Аналитик :: analyze (session={session_id})\n{'='*80}\n\n")
        f.write("--- INPUT MESSAGE ---\n")
        f.write(f"{message}\n\n")
        f.write("--- OUTPUT ---\n")
        f.write(f"{json.dumps(result, ensure_ascii=False, indent=2)[:5000]}\n\n")

_session_manager = SessionManager()
_orchestrator = AnalystOrchestrator()


@router.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "module": "analyst",
        "components": {"gateway": "ok", "orchestrator": "ok"},
    }


class AnalyzeRequest(BaseModel):
    session_id: str
    message: str


async def _validate_with_mval(*, session_id: str, concretized_request: dict[str, Any]) -> dict[str, Any] | None:
    """Опциональная валидация через модуль `mval` (не прерывает диалог при ошибках)."""
    try:
        artifact = concretized_request.get("concretized_request", concretized_request)
        body = {
            "phase": "ARCHITECTURE",
            "source_module": "analyst",
            "target_module": "architecture",
            "artifact": artifact,
            "metadata": {"session_id": session_id},
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{MVAL_BASE_URL.rstrip('/')}{MVAL_VALIDATE_PATH}", json=body)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


@router.post("/analyze")
async def analyze(body: AnalyzeRequest) -> dict[str, Any]:
    pipeline_log(
        body.session_id,
        "gateway",
        "http_analyze_in",
        message_chars=len(body.message or ""),
        message_preview=(body.message or "")[:180],
    )
    session_state = _session_manager.get_or_create(body.session_id)
    result = await _orchestrator.process_message(session_state, body.message)

    _log_analyst(body.session_id, body.message, result)

    if result.get("kind") == "final" and isinstance(result.get("concretized_request"), dict):
        pipeline_log(body.session_id, "gateway→mval", "validate_attempt", target=f"{MVAL_BASE_URL.rstrip('/')}{MVAL_VALIDATE_PATH}")
        mval_verdict = await _validate_with_mval(
            session_id=body.session_id,
            concretized_request=result["concretized_request"],
        )
        if mval_verdict is not None:
            result["mval_verdict"] = mval_verdict
            pipeline_log(body.session_id, "gateway←mval", "validate_ok", keys=list(mval_verdict.keys())[:20])
        else:
            pipeline_log(body.session_id, "gateway←mval", "validate_skip_or_failed", note="no_verdict")

    pipeline_log(
        body.session_id,
        "gateway",
        "http_analyze_out",
        kind=result.get("kind"),
        has_mval="mval_verdict" in result,
    )
    return result


@router.websocket("/ws/{session_id}")
async def ws_endpoint(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    session_state = _session_manager.get_or_create(session_id)

    try:
        while True:
            text = await websocket.receive_text()
            pipeline_log(session_id, "gateway", "ws_message_in", message_chars=len(text or ""), message_preview=(text or "")[:180])
            result = await _orchestrator.process_message(session_state, text)

            if result.get("kind") == "final" and isinstance(result.get("concretized_request"), dict):
                mval_verdict = await _validate_with_mval(
                    session_id=session_id,
                    concretized_request=result["concretized_request"],
                )
                if mval_verdict is not None:
                    result["mval_verdict"] = mval_verdict

            pipeline_log(session_id, "gateway", "ws_message_out", kind=result.get("kind"))
            await websocket.send_json(result)
    except WebSocketDisconnect:
        return

