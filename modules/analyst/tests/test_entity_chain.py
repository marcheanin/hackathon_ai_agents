from __future__ import annotations

import asyncio

from analyst.chains.entities import extract_entities


def test_entity_extractor_portal_sms_adds_supply_chain_and_nfr() -> None:
    msg = (
        "Нужен портал тикетов для банков-клиентов, до 100к обращений в месяц, "
        "с подтверждением по SMS. SBOM и CVE. RPS 500 пик 2000 задержка до 3 сек"
    )
    res = asyncio.run(extract_entities(user_message=msg, conversation_history=[], existing_entities=None, domain_hint=None))
    caps = set(res.entities.capabilities)
    assert "sms_sending" in caps
    assert "sms_confirm" in caps
    assert "client_ticket_ingest" in caps
    assert "vulnerability_scan" in caps
    assert res.entities.transfer_mode is None
    assert res.entities.nfr is not None
    assert res.entities.nfr.rps == 500
