from __future__ import annotations

import asyncio

from analyst.orchestrator import AnalystOrchestrator
from analyst.session import SessionManager


def test_e2e_force_finalize_after_max_iterations(orchestrator: AnalystOrchestrator, session_manager: SessionManager) -> None:
    session = session_manager.get_or_create("sess_force_finalize")

    msg_no_nfr = (
        "Нужен портал тикетов для банков-клиентов, до 100к обращений в месяц, "
        "с подтверждением по SMS. REST webhook. Со счёта на счёт интеграция."
    )
    out = asyncio.run(orchestrator.process_message(session, msg_no_nfr))
    assert out["kind"] == "clarification"

    # Дальше несколько итераций без заполнения NFR (rps/latency)
    for _ in range(5):
        out = asyncio.run(orchestrator.process_message(session, "RPS не определён, задержка не задана."))

    assert out["kind"] == "final"
    assert out.get("force_finalize") is True
    concretized = out["concretized_request"]
    assert concretized["concretized_request"]["meta"]["unresolved_gaps"]

