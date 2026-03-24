from __future__ import annotations

from uuid import UUID

import structlog

from mval.domain.models import ValidationContext, ValidationVerdict

logger = structlog.get_logger("mval.audit")


class AuditLogger:
    """Structured audit logging to stdout (JSON lines)."""

    def log_request(self, context: ValidationContext) -> None:
        logger.info(
            "validation.request",
            correlation_id=str(context.correlation_id),
            phase=context.phase,
            source_module=context.source_module,
            target_module=context.target_module,
        )

    def log_verdict(self, verdict: ValidationVerdict) -> None:
        logger.info(
            "validation.verdict",
            correlation_id=str(verdict.correlation_id),
            phase=verdict.phase,
            verdict=verdict.verdict,
            duration_ms=verdict.duration_ms,
            red_team_available=verdict.red_team_available,
            passed=verdict.compliance_report.passed_count,
            failed=verdict.compliance_report.failed_count,
            threat_count=len(verdict.threat_findings),
        )

    def log_error(
        self, correlation_id: UUID, error: str, detail: dict | None = None
    ) -> None:
        logger.error(
            "validation.error",
            correlation_id=str(correlation_id),
            error=error,
            detail=detail or {},
        )


def configure_logging() -> None:
    """Configure structlog for JSON stdout output."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(0),
        cache_logger_on_first_use=True,
    )
