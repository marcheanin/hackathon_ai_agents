from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from mval.domain.enums import (
    PolicyCategory,
    SeverityLevel,
    ValidationPhase,
    VerdictType,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Request / Response DTOs ──────────────────────────────────────────


class ValidationRequest(BaseModel):
    """HTTP request body for POST /validate."""

    phase: ValidationPhase
    source_module: str
    target_module: str
    artifact: dict
    metadata: dict = Field(default_factory=dict)


class ValidationContext(BaseModel):
    """Internal enriched context passed through the validation pipeline."""

    correlation_id: UUID = Field(default_factory=uuid4)
    phase: ValidationPhase
    source_module: str
    target_module: str
    artifact: dict
    timestamp: datetime = Field(default_factory=_utcnow)
    metadata: dict = Field(default_factory=dict)


# ── Policy ───────────────────────────────────────────────────────────


class PolicyRule(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    phase: ValidationPhase
    category: PolicyCategory
    severity: SeverityLevel
    rule_expression: str
    expected_value: str | None = None
    description: str
    enabled: bool = True
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class PolicyRuleCreate(BaseModel):
    """Payload for creating a new policy rule via API."""

    name: str
    phase: ValidationPhase
    category: PolicyCategory
    severity: SeverityLevel
    rule_expression: str
    expected_value: str | None = None
    description: str
    enabled: bool = True


# ── Compliance ───────────────────────────────────────────────────────


class ComplianceCheckResult(BaseModel):
    rule_id: UUID
    rule_name: str
    passed: bool
    severity: SeverityLevel
    detail: str


class ComplianceReport(BaseModel):
    phase: ValidationPhase
    results: list[ComplianceCheckResult] = Field(default_factory=list)
    passed_count: int = 0
    failed_count: int = 0
    highest_severity: SeverityLevel | None = None


# ── Threat Findings (Red Teaming) ────────────────────────────────────


class ThreatFinding(BaseModel):
    finding_id: UUID = Field(default_factory=uuid4)
    threat_name: str
    description: str
    severity: SeverityLevel
    attack_vector: str
    mitigation: str
    confidence: float = Field(ge=0.0, le=1.0)


# ── Final Verdict ────────────────────────────────────────────────────


class ValidationVerdict(BaseModel):
    correlation_id: UUID
    phase: ValidationPhase
    verdict: VerdictType
    compliance_report: ComplianceReport
    threat_findings: list[ThreatFinding] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    red_team_available: bool = True
    duration_ms: float
    timestamp: datetime = Field(default_factory=_utcnow)
