from __future__ import annotations

import asyncio

from analyst.orchestrator import AnalystOrchestrator
from analyst.session import SessionManager


def test_e2e_exhaustive_single_turn_synthesizes(orchestrator: AnalystOrchestrator, session_manager: SessionManager) -> None:
    session = session_manager.get_or_create("sess_exhaustive")

    msg1 = (
        "Нужен портал тикетов для банков-клиентов, до 100к обращений в месяц, с подтверждением по SMS. "
        "SBOM и CVE, CVSS>=7. RPS 500, пик 2000, задержка до 3 сек. REST webhook. "
        "Со счёта на счёт интеграция. Автоотмена через 10 минут."
    )

    out1 = asyncio.run(orchestrator.process_message(session, msg1))
    assert out1["kind"] == "final", out1

