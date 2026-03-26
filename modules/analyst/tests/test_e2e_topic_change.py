from __future__ import annotations

import asyncio

from analyst.orchestrator import AnalystOrchestrator
from analyst.session import SessionManager

def test_e2e_topic_change_overwrites_entities_but_keeps_iteration(
    orchestrator: AnalystOrchestrator,
    session_manager: SessionManager,
) -> None:
    session = session_manager.get_or_create("sess_topic_change")

    msg1 = (
        "Нужен портал тикетов для банков-клиентов, до 100к обращений в месяц, "
        "с подтверждением по SMS. SBOM и CVE для релизов."
    )
    out1 = asyncio.run(orchestrator.process_message(session, msg1))
    assert out1["kind"] == "clarification"
    assert int(session["iteration"]) == 1

    msg2 = "RPS 500, пик 2000, задержка до 3 сек. Со счёта на счёт."
    out2 = asyncio.run(orchestrator.process_message(session, msg2))
    assert out2["kind"] == "clarification"
    assert int(session["iteration"]) == 2

    msg3 = "Нужна внутренняя git-платформа с merge request и branch protection."
    out3 = asyncio.run(orchestrator.process_message(session, msg3))
    assert out3["kind"] in {"clarification", "redirect_choice"}
    assert int(session["iteration"]) >= 2

    extracted_entities = session.get("extracted_entities")
    if hasattr(extracted_entities, "capabilities"):
        assert "client_ticket_ingest" not in set(extracted_entities.capabilities or [])

