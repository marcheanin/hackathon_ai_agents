from __future__ import annotations

import asyncio

from analyst.models.context import EnrichedContext
from analyst.models.entities import DomainInfo, ExtractedEntities
from analyst.observability import pipeline_log
from analyst.enrichment.agent_catalog import search_agent_candidates
from analyst.enrichment.code_knowledge import search_snippets
from analyst.enrichment.knowledge_retrieval import retrieve_knowledge_hits
from analyst.enrichment.mcp_client import fetch_mcp_data
from analyst.enrichment.tool_discovery import discover_tools


class ContextEnricher:
    async def enrich_context(
        self,
        domain: DomainInfo,
        entities: ExtractedEntities,
        *,
        session_id: str | None = None,
    ) -> EnrichedContext:
        """Собирает EnrichedContext (частично при деградации)."""

        sid = session_id or "?"
        caps = list(entities.capabilities or [])
        pipeline_log(
            sid,
            "enrichment",
            "enrich_context_start",
            domain=domain.domain,
            sub_domain=domain.sub_domain,
            capabilities_count=len(caps),
            capabilities_sample=caps[:12],
        )

        mcp_task = fetch_mcp_data(domain, entities, session_id=sid)
        agents_task = search_agent_candidates(domain, entities)
        snippets_task = search_snippets(domain, entities)
        tools_task = discover_tools(domain, entities)
        knowledge_task = retrieve_knowledge_hits(domain=domain, entities=entities)

        (mcp_data, mcp_errors), agent_candidates, snippet_matches, tool_list, knowledge_hits = await asyncio.gather(
            mcp_task, agents_task, snippets_task, tools_task, knowledge_task
        )

        pipeline_log(
            sid,
            "enrichment",
            "enrich_context_done",
            agent_candidates=len(agent_candidates),
            snippets=len(snippet_matches),
            tools=len(tool_list),
            mcp_keys=list(mcp_data.keys()),
            knowledge_hits=len(knowledge_hits),
        )

        # В EnrichedContext на этом этапе мы фиксируем “кандидатов”.
        # Agent Match Evaluator и sufficiency/clarification будут ниже.
        return EnrichedContext(
            mcp_data=mcp_data,
            agent_candidates=agent_candidates,
            agent_matches=[],
            snippet_matches=snippet_matches,
            tool_list=tool_list,
            mcp_errors=mcp_errors,
            knowledge_hits=knowledge_hits,
        )

