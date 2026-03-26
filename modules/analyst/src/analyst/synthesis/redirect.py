from __future__ import annotations

from analyst.models.agents import AgentMatch, AgentEntry
from analyst.models.context import EnrichedContext
from analyst.models.redirect import RedirectApi, RedirectResponse


def _find_agent(enriched_context: EnrichedContext, agent_id: str) -> AgentEntry | None:
    for a in enriched_context.agent_candidates:
        if a.id == agent_id:
            return a
    return None


def build_redirect_response(enriched_context: EnrichedContext, best_match: AgentMatch) -> RedirectResponse:
    agent = _find_agent(enriched_context, best_match.agent_id)
    if agent is None:
        return RedirectResponse(
            agent_name=best_match.agent_id,
            owner_team=None,
            contact=None,
            api=RedirectApi(base_url=""),
            mcp_server_uri=None,
            docs_url=None,
            auth_notes=None,
            decision="redirect",
        )

    return RedirectResponse(
        agent_name=agent.name,
        owner_team=agent.owner_team,
        contact=agent.contact,
        api=RedirectApi(base_url=agent.api.base_url),
        mcp_server_uri=agent.mcp_server_uri,
        docs_url=agent.api.docs_url,
        auth_notes=agent.api.auth,
        decision="redirect",
    )

