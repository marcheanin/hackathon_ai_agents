from __future__ import annotations

from typing import Sequence

from analyst.config import AGENT_PARTIAL_MATCH_THRESHOLD
from analyst.models.context import EnrichedContext, MonitoringInfo, TeamStandards, TemplateRef
from analyst.models.entities import NFR
from analyst.models.enums import ConcretizedDecision
from analyst.models.agents import AgentMatch, AgentOverlapAnalysis, ExistingAgentRef
from analyst.models.entities import ExtractedEntities
from analyst.models.context import EnrichedContext
from analyst.models.entities import DomainInfo
from analyst.models.request import ConcretizedMeta, ConcretizedNFR, ConcretizedRequest, ConcretizedRequestPayload


def _build_team_standards(enriched_context: EnrichedContext) -> TeamStandards | None:
    team = enriched_context.mcp_data.get("team") if enriched_context.mcp_data else None
    if not isinstance(team, dict):
        return None
    return TeamStandards(
        language=team.get("language"),
        framework=team.get("framework"),
        code_style=team.get("code_style"),
    )


def _build_monitoring(enriched_context: EnrichedContext) -> MonitoringInfo | None:
    monitoring = enriched_context.mcp_data.get("monitoring") if enriched_context.mcp_data else None
    if not isinstance(monitoring, dict):
        return None
    return MonitoringInfo(required=monitoring.get("required", []), sla_alerting=monitoring.get("sla_alerting"))


def _select_existing_agents(enriched_context: EnrichedContext, agent_matches: Sequence[AgentMatch]) -> list[ExistingAgentRef]:
    existing: list[ExistingAgentRef] = []
    for m in agent_matches:
        # В MVP считаем "переиспользуемым" даже частичное пересечение capabilities.
        if m.coverage_score <= 0:
            continue
        # Находим исходного агента в agent_candidates, чтобы получить api и composition_hint
        agent_entry = next((a for a in enriched_context.agent_candidates if a.id == m.agent_id), None)
        if agent_entry is None:
            continue
        composition_hint = agent_entry.composition_hints[0] if agent_entry.composition_hints else None
        existing.append(
            ExistingAgentRef(
                id=agent_entry.id,
                name=agent_entry.name,
                coverage_score=m.coverage_score,
                covered_capabilities=m.covered_capabilities,
                composition_hint=composition_hint,
                api=agent_entry.api.base_url,
                mcp_uri=agent_entry.mcp_server_uri,
                protocol=agent_entry.api.protocol,
                auth=agent_entry.api.auth,
            )
        )
    return existing


def synthesize_request(
    *,
    extracted_entities: ExtractedEntities,
    domain: DomainInfo,
    enriched_context: EnrichedContext,
    session_id: str,
    iterations: int,
    confidence_score: int,
    unresolved_gaps: list[str],
    intent: str,
) -> ConcretizedRequest:
    # Agent reuse section
    agent_matches = enriched_context.agent_matches
    existing_agents = _select_existing_agents(enriched_context, agent_matches)

    total_required = len(set(extracted_entities.capabilities or []))
    covered = len(set.union(*(set(a.covered_capabilities) for a in existing_agents))) if existing_agents and total_required else 0
    to_build = max(total_required - covered, 0)
    reuse_percentage = (covered / total_required * 100.0) if total_required else None

    agent_overlap = None
    if total_required:
        agent_overlap = AgentOverlapAnalysis(
            total_capabilities_required=total_required,
            covered_by_existing_agents=covered,
            to_build_from_scratch=to_build,
            reuse_percentage=reuse_percentage,
        )

    # Team standards & monitoring from mcp_data
    enriched_context_out = enriched_context.model_copy(deep=True)
    enriched_context_out.existing_agents = existing_agents
    enriched_context_out.agent_overlap_analysis = agent_overlap
    enriched_context_out.team_standards = _build_team_standards(enriched_context_out)
    enriched_context_out.monitoring = _build_monitoring(enriched_context_out)

    # Code templates from snippet_matches
    enriched_context_out.available_templates = [
        TemplateRef(id=s.id, summary=s.summary, relevance=str(s.complexity or "high")) for s in (enriched_context_out.snippet_matches or [])
    ]

    decision = ConcretizedDecision.build_with_agent_reuse if existing_agents else ConcretizedDecision.build_new

    nfr_obj = extracted_entities.nfr if extracted_entities.nfr is not None else NFR()

    payload = ConcretizedRequestPayload(
        meta=ConcretizedMeta(
            session_id=session_id,
            iterations=iterations,
            confidence_score=confidence_score,
            unresolved_gaps=unresolved_gaps,
            decision=decision,
        ),
        intent=intent,
        domain=domain.domain,
        sub_domain=domain.sub_domain,
        system_name=extracted_entities.system_name,
        business_requirements=extracted_entities.business_requirements or [],
        nfr=nfr_obj,
        integrations=extracted_entities.integrations or [],
        constraints=extracted_entities.constraints,
        enriched_context=enriched_context_out,
    )

    return ConcretizedRequest(concretized_request=payload)

