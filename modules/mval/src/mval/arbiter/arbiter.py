from __future__ import annotations

from mval.domain.enums import SEVERITY_ORDER, SeverityLevel, VerdictType
from mval.domain.models import (
    ComplianceReport,
    ThreatFinding,
    ValidationContext,
    ValidationVerdict,
)


class ValidationArbiter:
    """Deterministic arbiter — pure function, no I/O.

    Verdict rules:
        1. Any CRITICAL compliance failure → FAIL
        2. Any CRITICAL threat finding (confidence >= 0.7) → FAIL
        3. Any HIGH compliance failure or red_team_unavailable → CONDITIONAL_PASS
        4. Any HIGH threat finding (confidence >= 0.5) → CONDITIONAL_PASS
        5. Otherwise → PASS
    """

    def decide(
        self,
        context: ValidationContext,
        compliance_report: ComplianceReport,
        threat_findings: list[ThreatFinding],
        red_team_available: bool,
        duration_ms: float,
    ) -> ValidationVerdict:
        recommendations: list[str] = []
        verdict = VerdictType.PASS

        # ── Evaluate compliance failures ──
        for result in compliance_report.results:
            if not result.passed:
                if result.severity == SeverityLevel.CRITICAL:
                    verdict = VerdictType.FAIL
                    recommendations.append(
                        f"[CRITICAL] Fix: {result.rule_name} — {result.detail}"
                    )
                elif result.severity == SeverityLevel.HIGH and verdict != VerdictType.FAIL:
                    verdict = VerdictType.CONDITIONAL_PASS
                    recommendations.append(
                        f"[HIGH] Review: {result.rule_name} — {result.detail}"
                    )

        # ── Evaluate threat findings ──
        for finding in threat_findings:
            if (
                finding.severity == SeverityLevel.CRITICAL
                and finding.confidence >= 0.7
            ):
                verdict = VerdictType.FAIL
                recommendations.append(
                    f"[THREAT/CRITICAL] {finding.threat_name}: {finding.mitigation}"
                )
            elif (
                finding.severity == SeverityLevel.HIGH
                and finding.confidence >= 0.5
                and verdict != VerdictType.FAIL
            ):
                verdict = VerdictType.CONDITIONAL_PASS
                recommendations.append(
                    f"[THREAT/HIGH] {finding.threat_name}: {finding.mitigation}"
                )

        # ── Red Team unavailability ──
        if not red_team_available and verdict != VerdictType.FAIL:
            verdict = VerdictType.CONDITIONAL_PASS
            recommendations.append(
                "Red Teaming agent was unavailable. Re-run validation when the agent is restored."
            )

        return ValidationVerdict(
            correlation_id=context.correlation_id,
            phase=context.phase,
            verdict=verdict,
            compliance_report=compliance_report,
            threat_findings=threat_findings,
            recommendations=recommendations,
            red_team_available=red_team_available,
            duration_ms=duration_ms,
        )
