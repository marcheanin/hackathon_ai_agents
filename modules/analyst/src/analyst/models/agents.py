from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from analyst.models.enums import AgentDecisionContribution


class AgentApiInfo(BaseModel):
    protocol: str
    base_url: str
    auth: str | None = None
    rate_limit: str | None = None
    docs_url: str | None = None


class AgentSLA(BaseModel):
    availability_percent: float | None = None
    latency_p99_ms: int | None = None
    support_hours: str | None = None


class AgentUsageStats(BaseModel):
    monthly_requests: int | None = None
    active_consumers: int | None = None


class AgentEntry(BaseModel):
    # Identification
    id: str
    name: str
    version: str
    status: str | None = None

    # Description & categorization
    description: str | None = None
    domain: str
    sub_domain: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    # Contract schemas
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)

    # Access
    api: AgentApiInfo
    mcp_server_uri: str | None = None
    owner_team: str | None = None
    contact: str | None = None
    sla: AgentSLA | None = None

    # Composition / dependencies
    dependencies: list[str] = Field(default_factory=list)
    composable: bool | None = None
    composition_hints: list[str] = Field(default_factory=list)

    # Metadata
    created_at: datetime | None = None
    last_updated: datetime | None = None
    usage_stats: AgentUsageStats | None = None


class AgentMatch(BaseModel):
    agent_id: str
    coverage_score: float = Field(ge=0.0, le=100.0)
    covered_capabilities: list[str] = Field(default_factory=list)
    uncovered_capabilities: list[str] = Field(default_factory=list)
    decision_contribution: AgentDecisionContribution


class AgentOverlapAnalysis(BaseModel):
    total_capabilities_required: int
    covered_by_existing_agents: int
    to_build_from_scratch: int | None = None
    reuse_percentage: float | None = None


class ExistingAgentRef(BaseModel):
    """Секция `enriched_context.existing_agents[]` для синтеза ConcretizedRequest."""

    id: str
    name: str
    coverage_score: float = Field(ge=0.0, le=100.0)
    covered_capabilities: list[str] = Field(default_factory=list)
    composition_hint: str | None = None

    # Access / integration
    api: str | None = None
    mcp_uri: str | None = None
    protocol: str | None = None
    auth: str | None = None

