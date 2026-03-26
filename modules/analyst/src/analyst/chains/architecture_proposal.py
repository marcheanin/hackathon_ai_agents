from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from analyst.chains.llm_client import LLMClient
from analyst.config import LLM_MODE
from analyst.models.context import EnrichedContext
from analyst.models.entities import DomainInfo, ExtractedEntities


class ArchitectureProposal(BaseModel):
    summary: str
    components: list[str] = Field(default_factory=list)
    integration_points: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


def _prompt_text() -> str:
    path = Path(__file__).resolve().parents[1] / "prompts" / "architecture_proposal.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return "Propose high-level architecture JSON only."


async def propose_architecture(
    *,
    extracted_entities: ExtractedEntities,
    domain: DomainInfo,
    enriched_context: EnrichedContext,
) -> ArchitectureProposal:
    if LLM_MODE != "mock":
        try:
            payload = await LLMClient().call_structured(
                system_prompt=_prompt_text(),
                user_prompt=(
                    f"domain: {domain.domain}/{domain.sub_domain}\n"
                    f"entities: {extracted_entities.model_dump()}\n"
                    f"available_tools: {enriched_context.tool_list}\n"
                    f"mcp_data_keys: {list((enriched_context.mcp_data or {}).keys())}\n"
                    f"closest_agents: {[a.model_dump() for a in enriched_context.agent_candidates[:5]]}\n"
                ),
                response_model=ArchitectureProposal,
            )
            assert isinstance(payload, ArchitectureProposal)
            return payload
        except Exception:
            pass
    return ArchitectureProposal(
        summary="No existing agent fully matches; propose a composable service with API ingress, orchestration core, and policy/security adapters.",
        components=[
            "API ingress layer",
            "Domain orchestration service",
            "Policy/compliance adapters",
            "Observability and audit module",
        ],
        integration_points=["Existing CI/CD", "Task tracker", "Internal knowledge base", "Security scanning APIs"],
        risks=["Ambiguous scope boundaries", "Missing NFR targets", "Tool ownership undefined"],
    )
