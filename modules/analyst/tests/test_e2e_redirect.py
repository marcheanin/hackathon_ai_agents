from __future__ import annotations

import asyncio

from analyst.orchestrator import AnalystOrchestrator
from analyst.session import SessionManager


def test_e2e_redirect_exact_match(orchestrator: AnalystOrchestrator, session_manager: SessionManager) -> None:
    session = session_manager.get_or_create("sess_redirect")

    msg1 = "Нужен агент для SBOM, аудита зависимостей и проверки CVE перед релизом для банка"
    out1 = asyncio.run(orchestrator.process_message(session, msg1))
    assert out1["kind"] == "redirect_choice"
    assert out1["agent_id"] == "agent_supply_chain_security"

    msg2 = "Да, перенаправьте (redirect)."
    out2 = asyncio.run(orchestrator.process_message(session, msg2))
    assert out2["kind"] == "redirect"
    redirect_response = out2["redirect_response"]
    assert redirect_response["agent_name"] == "Supply Chain Security Scanner"

