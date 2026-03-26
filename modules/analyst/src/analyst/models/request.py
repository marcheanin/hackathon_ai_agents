from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from analyst.models.context import EnrichedContext
from analyst.models.entities import Constraints, Integration, NFR
from analyst.models.enums import ConcretizedDecision, IntentType


class ConcretizedMeta(BaseModel):
    session_id: str
    iterations: int
    confidence_score: int = Field(ge=0, le=100)
    unresolved_gaps: list[str] = Field(default_factory=list)
    decision: ConcretizedDecision


class ConcretizedNFR(BaseModel):
    rps: int
    peak_rps: int
    sla_percent: float | None = None
    latency_p99_ms: int | None = None
    idempotency: str


class ConcretizedRequestPayload(BaseModel):
    meta: ConcretizedMeta

    intent: IntentType | str
    domain: str
    sub_domain: str | None = None
    system_name: str | None = None

    business_requirements: list[str] = Field(default_factory=list)
    nfr: ConcretizedNFR | NFR
    integrations: list[Integration] = Field(default_factory=list)
    constraints: Constraints | None = None

    enriched_context: EnrichedContext = Field(default_factory=EnrichedContext)


class ConcretizedRequest(BaseModel):
    """Контейнер с ключом `concretized_request` согласно contracts.md."""

    concretized_request: ConcretizedRequestPayload

