from __future__ import annotations

import pytest

import sys
import os
from pathlib import Path

# Добавляем modules/analyst/src в PYTHONPATH для импортов `analyst.*`
SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Стабилизируем тесты: всегда mock-режим LLM.
os.environ["ANALYST_LLM_MODE"] = "mock"

from analyst.orchestrator import AnalystOrchestrator
from analyst.session import SessionManager


@pytest.fixture(autouse=True)
def _force_deterministic_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Конфиг читается при импорте; для e2e фиксируем mock-режим в цепочке intent."""
    monkeypatch.setattr("analyst.chains.intent.LLM_MODE", "mock")


@pytest.fixture(scope="session")
def orchestrator() -> AnalystOrchestrator:
    return AnalystOrchestrator()


@pytest.fixture
def session_manager() -> SessionManager:
    return SessionManager(ttl_seconds=3600)

