from __future__ import annotations

from typing import Any

from analyst.models.entities import DomainInfo, ExtractedEntities
from analyst.models.agents import AgentEntry
from analyst.mcp_servers.agent_registry import search_agents


async def search_agent_candidates(domain: DomainInfo, extracted_entities: ExtractedEntities) -> list[AgentEntry]:
    """Поиск кандидатов агентов в Agent Registry (MCP синтетика)."""

    candidate_dicts: list[dict[str, Any]] = await search_agents(
        # Часть capabilities может закрываться агентами из смежных доменов (тикеты + SBOM и т.д.),
        # поэтому домен в поиске нестрогий.
        domain=None,
        capabilities=extracted_entities.capabilities or None,
        tags=None,
        status="active",
    )
    return [AgentEntry.model_validate(a) for a in candidate_dicts]

