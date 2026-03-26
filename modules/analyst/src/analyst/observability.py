"""Структурированные логи пайплайна (узлы оркестратора, enrichment, gateway, MCP).

Включение: ANALYST_PIPELINE_LOG=true (по умолчанию). Отключить: false/0/no.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from analyst.config import PIPELINE_LOG_ENABLED

_log = logging.getLogger("analyst.pipeline")
_CONFIGURED = False


def _ensure_logger_configured() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    # Ensure the pipeline logger is actually visible on console.
    _log.setLevel(logging.INFO)
    _log.disabled = False
    _log.propagate = True
    if not _log.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(message)s"))
        _log.addHandler(handler)
    _CONFIGURED = True


def _safe_json(data: dict[str, Any]) -> str:
    try:
        return json.dumps(data, ensure_ascii=False, default=str)
    except TypeError:
        return repr(data)


def pipeline_log(session_id: str, module: str, event: str, **data: Any) -> None:
    """Одна строка: session | module | event | JSON payload."""
    if not PIPELINE_LOG_ENABLED:
        return
    _ensure_logger_configured()
    sid = (session_id or "?")[:40]
    snippet = _safe_json({k: v for k, v in data.items() if v is not None})
    if len(snippet) > 2400:
        snippet = snippet[:2397] + "..."
    _log.info("%s | %s | %s | %s", sid, module, event, snippet)
