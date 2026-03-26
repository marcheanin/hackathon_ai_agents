from __future__ import annotations

import asyncio

from analyst.orchestrator import AnalystOrchestrator
from analyst.session import SessionManager


def test_e2e_mcp_down_forces_clarification(monkeypatch, orchestrator: AnalystOrchestrator, session_manager: SessionManager) -> None:
    async def fake_fetch_mcp_data(domain, entities, **kwargs):
        return {}, ["mcp_down"]

    # Важно: patch делаем в том модуле, откуда функция импортирована в enricher.py
    monkeypatch.setattr("analyst.enrichment.enricher.fetch_mcp_data", fake_fetch_mcp_data)

    session = session_manager.get_or_create("sess_mcp_down")

    msg1 = (
        "Нужен портал тикетов для банков-клиентов, до 100к обращений в месяц, с подтверждением по SMS. "
        "SBOM CVE CVSS>=7. RPS 500, пик 2000, задержка до 3 сек. REST webhook. Со счёта на счёт. Автоотмена через 10 минут."
    )

    out1 = asyncio.run(orchestrator.process_message(session, msg1))
    assert out1["kind"] == "clarification"

