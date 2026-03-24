from __future__ import annotations

import asyncio
import time

import httpx
import structlog

from mval.arbiter.arbiter import ValidationArbiter
from mval.config import settings
from mval.domain.enums import VerdictType
from mval.domain.models import (
    ComplianceReport,
    ThreatFinding,
    ValidationContext,
    ValidationVerdict,
)
from mval.logging.audit import AuditLogger
from mval.policy.engine import PolicyEngine

logger = structlog.get_logger("mval.architecture_validator")


class ArchitectureValidator:
    """Validates МАРХ architecture artifacts.

    Hybrid: runs deterministic PolicyEngine + AI RedTeamAgent in parallel
    via asyncio.gather. Red Team is called through the sidecar HTTP API.
    """

    def __init__(
        self,
        policy_engine: PolicyEngine,
        arbiter: ValidationArbiter,
        audit: AuditLogger,
        redteam_url: str | None = None,
        redteam_timeout: int | None = None,
    ) -> None:
        self._engine = policy_engine
        self._arbiter = arbiter
        self._audit = audit
        self._redteam_url = redteam_url or settings.redteam_url
        self._redteam_timeout = redteam_timeout or settings.redteam_timeout_seconds

    async def _run_policy_check(
        self, context: ValidationContext
    ) -> ComplianceReport | Exception:
        try:
            return await self._engine.evaluate(context.phase, context.artifact)
        except Exception as exc:
            return exc

    async def _run_red_team(
        self, context: ValidationContext
    ) -> tuple[list[ThreatFinding], bool]:
        """Call the Red Teaming sidecar. Returns (findings, available)."""
        try:
            threat_matrix = await self._engine.get_threat_matrix()
            async with httpx.AsyncClient(timeout=self._redteam_timeout) as client:
                resp = await client.post(
                    f"{self._redteam_url}/analyze",
                    json={
                        "artifact": context.artifact,
                        "threat_matrix": [
                            t.model_dump(mode="json") for t in threat_matrix
                        ],
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            if data.get("error"):
                logger.warning("redteam_error", error=data["error"])
                return [], False

            findings = [ThreatFinding.model_validate(f) for f in data["findings"]]
            return findings, True

        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.warning("redteam_unavailable", error=str(exc))
            self._audit.log_error(
                context.correlation_id,
                "red_team_timeout",
                {"error": str(exc)},
            )
            return [], False
        except Exception as exc:
            logger.error("redteam_unexpected_error", error=str(exc))
            return [], False

    async def validate(self, context: ValidationContext) -> ValidationVerdict:
        start = time.monotonic()

        # Run policy check and red teaming in parallel
        policy_task = asyncio.create_task(self._run_policy_check(context))
        redteam_task = asyncio.create_task(self._run_red_team(context))

        policy_result, (threat_findings, red_team_available) = await asyncio.gather(
            policy_task, redteam_task
        )

        duration = (time.monotonic() - start) * 1000

        # Handle policy engine failure (fail-closed)
        if isinstance(policy_result, Exception):
            logger.error("policy_engine_unavailable", error=str(policy_result))
            self._audit.log_error(
                context.correlation_id,
                "policy_engine_unavailable",
                {"error": str(policy_result)},
            )
            report = ComplianceReport(
                phase=context.phase,
                results=[],
                passed_count=0,
                failed_count=1,
            )
            return ValidationVerdict(
                correlation_id=context.correlation_id,
                phase=context.phase,
                verdict=VerdictType.FAIL,
                compliance_report=report,
                threat_findings=threat_findings,
                recommendations=["Policy engine unavailable. Retry when БДвал is restored."],
                red_team_available=red_team_available,
                duration_ms=duration,
            )

        verdict = self._arbiter.decide(
            context=context,
            compliance_report=policy_result,
            threat_findings=threat_findings,
            red_team_available=red_team_available,
            duration_ms=duration,
        )
        self._audit.log_verdict(verdict)
        return verdict
