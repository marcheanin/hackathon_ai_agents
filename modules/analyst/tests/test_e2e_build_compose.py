from __future__ import annotations

import asyncio

from analyst.orchestrator import AnalystOrchestrator
from analyst.session import SessionManager


def test_e2e_vendor_portal_build_compose_existing_agents(orchestrator: AnalystOrchestrator, session_manager: SessionManager) -> None:
    session = session_manager.get_or_create("sess_vendor_portal")

    msg1 = (
        "Нужен портал тикетов для банков-клиентов, до 100к обращений в месяц, "
        "с подтверждением по SMS. SBOM и CVE для релизов, CVSS>=7."
    )
    out1 = asyncio.run(orchestrator.process_message(session, msg1))
    assert out1["kind"] in {"clarification", "redirect_choice"}  # обычно clarification

    msg2 = (
        "Портал тикетов банка-клиента: RPS 500, пик 2000, задержка до 3 сек. REST webhook. "
        "SBOM CVE. Со счёта на счёт интеграция с core банка. Автоотмена через 10 минут."
    )
    out2 = asyncio.run(orchestrator.process_message(session, msg2))
    assert out2["kind"] == "final", out2

    concretized = out2["concretized_request"]
    meta = concretized["concretized_request"]["meta"]
    assert meta["decision"] in {"build_with_agent_reuse", "build_new"}

    existing_agents = concretized["concretized_request"]["enriched_context"].get("existing_agents", [])
    agent_ids = {a.get("id") for a in existing_agents}
    assert "agent_bank_client_ticketing_hub" in agent_ids
    assert "agent_supply_chain_security" in agent_ids

