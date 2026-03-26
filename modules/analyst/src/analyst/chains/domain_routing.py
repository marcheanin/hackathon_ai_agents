from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from analyst.chains.llm_client import LLMClient
from analyst.config import LLM_MODE
from analyst.models.agents import AgentEntry, AgentMatch
from analyst.models.context import DomainCandidate, DomainLink
from analyst.models.entities import DomainInfo, ExtractedEntities


class DomainRoutingResult(BaseModel):
    primary: DomainInfo
    alternatives: list[DomainCandidate] = Field(default_factory=list)
    cross_domain_links: list[DomainLink] = Field(default_factory=list)
    reasoning: str = ""


class _LLMDomainRoutingPayload(BaseModel):
    primary_domain: str
    primary_sub_domain: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    alternatives: list[DomainCandidate] = Field(default_factory=list)
    cross_domain_links: list[DomainLink] = Field(default_factory=list)


def _load_relations() -> list[dict[str, str]]:
    path = Path(__file__).resolve().parents[1] / "data" / "domain_relations.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("relations", [])
    except Exception:
        return []


def _find_relations(primary_domain: str) -> list[DomainLink]:
    links: list[DomainLink] = []
    for rel in _load_relations():
        if rel.get("from_domain") == primary_domain:
            links.append(DomainLink.model_validate(rel))
    return links


def _heuristic_route(extracted_entities: ExtractedEntities) -> DomainRoutingResult:
    caps = set(extracted_entities.capabilities or [])

    primary = DomainInfo(domain="platform", sub_domain="internal_tools", confidence=0.45)
    alternatives: list[DomainCandidate] = []
    reason = "Default fallback."

    if {"client_ticket_ingest", "bank_sla_tracking", "webhook_ingestion"} & caps:
        primary = DomainInfo(domain="client_delivery", sub_domain="support_portal", confidence=0.88)
        reason = "Есть признаки клиентского support-портала."
        if {"vulnerability_scan", "sbom_validation", "dependency_audit"} & caps:
            alternatives.append(
                DomainCandidate(
                    domain="security_compliance",
                    sub_domain="supply_chain",
                    confidence=0.82,
                    reason="Есть требования CVE/SBOM.",
                )
            )
    elif {"vulnerability_scan", "sbom_validation", "dependency_audit"} & caps:
        primary = DomainInfo(domain="security_compliance", sub_domain="supply_chain", confidence=0.86)
        reason = "Есть security/supply-chain capabilities."
    elif {"repository_lifecycle", "merge_request_policy", "branch_protection"} & caps:
        primary = DomainInfo(domain="engineering_platform", sub_domain="git", confidence=0.84)
        reason = "Есть capabilities для git governance."
    elif {"pipeline_template_library", "build_artifact_signing", "deployment_gate"} & caps:
        primary = DomainInfo(domain="engineering_platform", sub_domain="cicd", confidence=0.83)
        reason = "Есть capabilities для CI/CD."
    elif {"work_item_sync", "sprint_velocity_export", "cross_tool_linking"} & caps:
        primary = DomainInfo(domain="engineering_platform", sub_domain="work_management", confidence=0.82)
        reason = "Есть capabilities для task/work management."
    elif {"documentation_search", "wiki_index", "semantic_doc_qa"} & caps:
        primary = DomainInfo(domain="product_knowledge", sub_domain="documentation", confidence=0.81)
        reason = "Есть признаки работы с документацией."
    elif {"product_line_registry", "semver_matrix", "eol_policy_check"} & caps:
        primary = DomainInfo(domain="product_knowledge", sub_domain="registry", confidence=0.8)
        reason = "Есть признаки реестра продуктов/версий."

    return DomainRoutingResult(
        primary=primary,
        alternatives=alternatives[:3],
        cross_domain_links=_find_relations(primary.domain),
        reasoning=reason,
    )


def _route_from_agents(
    *,
    agent_matches: list[AgentMatch] | None,
    candidate_agents: list[AgentEntry | dict[str, Any]] | None,
) -> DomainRoutingResult | None:
    if not agent_matches or not candidate_agents:
        return None
    best = max(agent_matches, key=lambda m: m.coverage_score, default=None)
    if best is None or best.coverage_score <= 0:
        return None
    by_id: dict[str, AgentEntry] = {}
    for agent in candidate_agents:
        if isinstance(agent, AgentEntry):
            by_id[agent.id] = agent
        else:
            parsed = AgentEntry.model_validate(agent)
            by_id[parsed.id] = parsed
    top_agent = by_id.get(best.agent_id)
    if top_agent is None:
        return None
    primary = DomainInfo(
        domain=top_agent.domain or "uncharted",
        sub_domain=top_agent.sub_domain,
        confidence=max(0.5, min(0.98, best.coverage_score / 100.0)),
    )
    alternatives: list[DomainCandidate] = []
    for match in sorted(agent_matches, key=lambda x: x.coverage_score, reverse=True):
        if match.agent_id == best.agent_id or match.coverage_score <= 0:
            continue
        a = by_id.get(match.agent_id)
        if not a:
            continue
        alternatives.append(
            DomainCandidate(
                domain=a.domain or "uncharted",
                sub_domain=a.sub_domain,
                confidence=max(0.2, min(0.95, match.coverage_score / 100.0)),
                reason=f"inferred from agent {a.id}",
            )
        )
        if len(alternatives) >= 3:
            break
    return DomainRoutingResult(
        primary=primary,
        alternatives=alternatives,
        cross_domain_links=_find_relations(primary.domain),
        reasoning=f"Derived from best matched agent `{top_agent.id}`.",
    )


def _prompt_text() -> str:
    path = Path(__file__).resolve().parents[1] / "prompts" / "domain_router.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return "Route to domain/sub_domain and return JSON only."


def _format_user_prompt(
    user_message: str,
    extracted_entities: ExtractedEntities,
    history: list[dict[str, Any]] | None,
    agent_matches: list[AgentMatch] | None,
    candidate_agents: list[AgentEntry | dict[str, Any]] | None,
) -> str:
    lines = [
        f"user_message: {user_message.strip()}",
        f"capabilities: {sorted(set(extracted_entities.capabilities or []))}",
    ]
    if history:
        lines.append(f"history_tail: {history[-6:]}")
    if agent_matches and candidate_agents:
        by_id: dict[str, AgentEntry] = {}
        for row in candidate_agents:
            if isinstance(row, AgentEntry):
                by_id[row.id] = row
            else:
                parsed = AgentEntry.model_validate(row)
                by_id[parsed.id] = parsed
        top = sorted(agent_matches, key=lambda m: m.coverage_score, reverse=True)[:5]
        shortlist: list[dict[str, Any]] = []
        for m in top:
            agent = by_id.get(m.agent_id)
            if not agent:
                continue
            shortlist.append(
                {
                    "id": agent.id,
                    "domain": agent.domain,
                    "sub_domain": agent.sub_domain,
                    "coverage_score": m.coverage_score,
                    "capabilities": agent.capabilities,
                }
            )
        if shortlist:
            lines.append(f"top_matched_agents: {shortlist}")
    return "\n".join(lines)


async def route_domain(
    *,
    user_message: str,
    extracted_entities: ExtractedEntities,
    conversation_history: list[dict[str, Any]] | None = None,
    llm_client: Any | None = None,
    agent_matches: list[AgentMatch] | None = None,
    candidate_agents: list[AgentEntry | dict[str, Any]] | None = None,
) -> DomainRoutingResult:
    from_agents = _route_from_agents(agent_matches=agent_matches, candidate_agents=candidate_agents)
    if from_agents is not None and LLM_MODE == "mock":
        return from_agents

    heuristic = _heuristic_route(extracted_entities)
    if from_agents is not None:
        heuristic = from_agents
    if LLM_MODE == "mock":
        return heuristic

    client: LLMClient = llm_client if llm_client is not None else LLMClient()
    try:
        payload = await client.call_structured(
            system_prompt=_prompt_text(),
            user_prompt=_format_user_prompt(
                user_message,
                extracted_entities,
                conversation_history,
                agent_matches,
                candidate_agents,
            ),
            response_model=_LLMDomainRoutingPayload,
        )
        assert isinstance(payload, _LLMDomainRoutingPayload)
        primary = DomainInfo(
            domain=payload.primary_domain,
            sub_domain=payload.primary_sub_domain,
            confidence=payload.confidence,
        )
        links = payload.cross_domain_links or _find_relations(primary.domain)
        alternatives = payload.alternatives[:3]
        if not alternatives and heuristic.alternatives:
            alternatives = heuristic.alternatives[:3]
        return DomainRoutingResult(
            primary=primary,
            alternatives=alternatives,
            cross_domain_links=links,
            reasoning=payload.reasoning,
        )
    except Exception:
        return heuristic
