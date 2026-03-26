from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from analyst.models.agents import AgentEntry, AgentMatch, AgentOverlapAnalysis, ExistingAgentRef
from analyst.models.snippets import SnippetSummary


class TemplateRef(BaseModel):
    id: str
    summary: str | None = None
    relevance: str | None = None


class TeamStandards(BaseModel):
    language: str | None = None
    framework: str | None = None
    code_style: str | None = None


class MonitoringInfo(BaseModel):
    required: list[str] = Field(default_factory=list)
    sla_alerting: bool | None = None


class DomainCandidate(BaseModel):
    domain: str
    sub_domain: str | None = None
    confidence: float | None = None
    reason: str | None = None


class DomainLink(BaseModel):
    from_domain: str
    to_domain: str
    relation: str
    rationale: str | None = None


class DynamicRequirement(BaseModel):
    id: str
    description: str
    required_fields: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    source: str = "dynamic"
    priority: str = "medium"
    activation_condition: str | None = None


class KnowledgeHit(BaseModel):
    source_type: str
    title: str
    excerpt: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class EnrichedContext(BaseModel):
    """Агрегат обогащения перед оценкой достаточности и синтезом."""

    # Raw sections
    mcp_data: dict[str, Any] = Field(default_factory=dict)
    agent_candidates: list[AgentEntry] = Field(default_factory=list)
    agent_matches: list[AgentMatch] = Field(default_factory=list)
    snippet_matches: list[SnippetSummary] = Field(default_factory=list)
    tool_list: list[str] = Field(default_factory=list)

    # Optional errors
    mcp_errors: list[str] = Field(default_factory=list)

    # Synthesizable sections (см. пример в contracts.md)
    existing_agents: list[ExistingAgentRef] = Field(default_factory=list)
    agent_overlap_analysis: AgentOverlapAnalysis | None = None
    available_templates: list[TemplateRef] = Field(default_factory=list)
    team_standards: TeamStandards | None = None
    monitoring: MonitoringInfo | None = None
    domain_candidates: list[DomainCandidate] = Field(default_factory=list)
    cross_domain_links: list[DomainLink] = Field(default_factory=list)
    dynamic_requirements: list[DynamicRequirement] = Field(default_factory=list)
    knowledge_hits: list[KnowledgeHit] = Field(default_factory=list)
    architecture_proposal: dict[str, Any] | None = None

