from __future__ import annotations

import time

import structlog

from mval.arbiter.arbiter import ValidationArbiter
from mval.domain.enums import VerdictType
from mval.domain.models import (
    ComplianceReport,
    ValidationContext,
    ValidationVerdict,
)
from mval.logging.audit import AuditLogger
from mval.policy.engine import PolicyEngine

logger = structlog.get_logger("mval.request_validator")


class RequestValidator:
    """Validates МАН request artifacts against policies (deterministic only)."""

    def __init__(
        self,
        policy_engine: PolicyEngine,
        arbiter: ValidationArbiter,
        audit: AuditLogger,
    ) -> None:
        self._engine = policy_engine
        self._arbiter = arbiter
        self._audit = audit

    async def validate(self, context: ValidationContext) -> ValidationVerdict:
        start = time.monotonic()
        try:
            report = await self._engine.evaluate(context.phase, context.artifact)
        except RuntimeError as exc:
            # fail-closed: PolicyEngine unavailable
            logger.error("policy_engine_unavailable", error=str(exc))
            self._audit.log_error(
                context.correlation_id,
                "policy_engine_unavailable",
                {"error": str(exc)},
            )
            duration = (time.monotonic() - start) * 1000
            report = ComplianceReport(
                phase=context.phase,
                results=[],
                passed_count=0,
                failed_count=1,
                highest_severity=None,
            )
            return ValidationVerdict(
                correlation_id=context.correlation_id,
                phase=context.phase,
                verdict=VerdictType.FAIL,
                compliance_report=report,
                recommendations=["Policy engine unavailable. Retry when БДвал is restored."],
                duration_ms=duration,
            )

        duration = (time.monotonic() - start) * 1000
        verdict = self._arbiter.decide(
            context=context,
            compliance_report=report,
            threat_findings=[],
            red_team_available=True,
            duration_ms=duration,
        )
        self._audit.log_verdict(verdict)
        return verdict
