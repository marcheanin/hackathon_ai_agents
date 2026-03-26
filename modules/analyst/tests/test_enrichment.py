from __future__ import annotations

import asyncio

from analyst.enrichment.enricher import ContextEnricher
from analyst.models.entities import DomainInfo, ExtractedEntities


def test_enrichment_returns_mcp_data_agents_and_snippets() -> None:
    enricher = ContextEnricher()
    domain = DomainInfo(domain="client_delivery", sub_domain="support_portal", confidence=0.8)
    extracted = ExtractedEntities(
        capabilities=[
            "client_ticket_ingest",
            "sms_sending",
            "sms_confirm",
            "vulnerability_scan",
            "sbom_validation",
            "dependency_audit",
        ],
        business_requirements=["Bank client ticketing ..."],
    )

    ctx = asyncio.run(enricher.enrich_context(domain, extracted))
    assert "apis" in ctx.mcp_data
    assert len(ctx.agent_candidates) > 0
    assert any(a.id == "agent_bank_client_ticketing_hub" for a in ctx.agent_candidates)
    assert any(a.id == "agent_supply_chain_security" for a in ctx.agent_candidates)
    assert any(s.id == "tmpl_bank_ticket_portal" for s in ctx.snippet_matches)

