from __future__ import annotations

from typing import Protocol
from uuid import UUID

from mval.domain.enums import ValidationPhase
from mval.domain.models import (
    ComplianceReport,
    PolicyRule,
    PolicyRuleCreate,
    ThreatFinding,
    ValidationContext,
    ValidationVerdict,
)


class IValidationGateway(Protocol):
    async def validate(self, context: ValidationContext) -> ValidationVerdict: ...
    async def health(self) -> dict: ...


class IRequestValidator(Protocol):
    async def validate(self, context: ValidationContext) -> ValidationVerdict: ...


class IArchitectureValidator(Protocol):
    async def validate(self, context: ValidationContext) -> ValidationVerdict: ...


class IPolicyEngine(Protocol):
    async def evaluate(
        self, phase: ValidationPhase, artifact: dict
    ) -> ComplianceReport: ...

    async def get_threat_matrix(self) -> list[PolicyRule]: ...


class IRedTeamAgent(Protocol):
    async def analyze(
        self, artifact: dict, threat_matrix: list[PolicyRule]
    ) -> list[ThreatFinding]: ...


class IValidationArbiter(Protocol):
    def decide(
        self,
        context: ValidationContext,
        compliance_report: ComplianceReport,
        threat_findings: list[ThreatFinding],
        red_team_available: bool,
        duration_ms: float,
    ) -> ValidationVerdict: ...


class IPolicyRepository(Protocol):
    async def get_rules(self, phase: ValidationPhase) -> list[PolicyRule]: ...
    async def get_rule(self, rule_id: UUID) -> PolicyRule | None: ...
    async def create_rule(self, rule: PolicyRuleCreate) -> PolicyRule: ...
    async def update_rule(self, rule_id: UUID, rule: PolicyRuleCreate) -> PolicyRule | None: ...
    async def delete_rule(self, rule_id: UUID) -> bool: ...
    async def list_rules(self) -> list[PolicyRule]: ...


class IAuditLogger(Protocol):
    def log_request(self, context: ValidationContext) -> None: ...
    def log_verdict(self, verdict: ValidationVerdict) -> None: ...
    def log_error(self, correlation_id: UUID, error: str, detail: dict | None = None) -> None: ...
