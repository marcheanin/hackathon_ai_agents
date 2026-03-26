from __future__ import annotations

import asyncio

from analyst.chains.agent_match import evaluate_agent_match
from analyst.mcp_servers.agent_registry import search_agents
from analyst.models.entities import ExtractedEntities


def test_agent_match_exact_for_supply_chain() -> None:
    extracted = ExtractedEntities(capabilities=["vulnerability_scan", "sbom_validation", "dependency_audit"])
    candidates = asyncio.run(search_agents(domain=None, capabilities=extracted.capabilities, tags=None, status="active"))
    res = asyncio.run(evaluate_agent_match(extracted_entities=extracted, candidate_agents=candidates))
    assert res.decision == "exact"
    assert res.best_match is not None
    assert res.best_match.coverage_score >= 90

