from __future__ import annotations

import asyncio

from analyst.enrichment.agent_catalog import search_agent_candidates
from analyst.models.entities import DomainInfo, ExtractedEntities


def test_agent_catalog_search_returns_supply_chain_for_vuln_capabilities() -> None:
    domain = DomainInfo(domain="security_compliance", sub_domain="supply_chain", confidence=0.7)
    extracted = ExtractedEntities(capabilities=["vulnerability_scan"])
    res = asyncio.run(search_agent_candidates(domain=domain, extracted_entities=extracted))
    assert any(a.id == "agent_supply_chain_security" for a in res)

