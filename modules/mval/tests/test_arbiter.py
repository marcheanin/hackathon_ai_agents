"""Tests for ValidationArbiter — deterministic verdict logic."""
from __future__ import annotations

from uuid import uuid4

from mval.arbiter.arbiter import ValidationArbiter
from mval.domain.enums import SeverityLevel, ValidationPhase, VerdictType
from mval.domain.models import (
    ComplianceCheckResult,
    ComplianceReport,
    ThreatFinding,
    ValidationContext,
)


def _context() -> ValidationContext:
    return ValidationContext(
        phase=ValidationPhase.REQUEST,
        source_module="МАН",
        target_module="МВАЛ",
        artifact={},
    )


def _report(results: list[ComplianceCheckResult] | None = None) -> ComplianceReport:
    results = results or []
    failed = [r for r in results if not r.passed]
    highest = None
    if failed:
        from mval.domain.enums import SEVERITY_ORDER
        highest = max(failed, key=lambda r: SEVERITY_ORDER[r.severity]).severity
    return ComplianceReport(
        phase=ValidationPhase.REQUEST,
        results=results,
        passed_count=len(results) - len(failed),
        failed_count=len(failed),
        highest_severity=highest,
    )


def _check(passed: bool, severity: SeverityLevel, name: str = "rule") -> ComplianceCheckResult:
    return ComplianceCheckResult(
        rule_id=uuid4(),
        rule_name=name,
        passed=passed,
        severity=severity,
        detail="test detail",
    )


def _threat(
    severity: SeverityLevel,
    confidence: float,
    name: str = "threat",
) -> ThreatFinding:
    return ThreatFinding(
        threat_name=name,
        description="test",
        severity=severity,
        attack_vector="test",
        mitigation="fix it",
        confidence=confidence,
    )


class TestArbiterAllPass:
    def test_all_rules_pass_gives_pass(self, arbiter: ValidationArbiter):
        results = [
            _check(True, SeverityLevel.LOW),
            _check(True, SeverityLevel.MEDIUM),
        ]
        verdict = arbiter.decide(_context(), _report(results), [], True, 10.0)
        assert verdict.verdict == VerdictType.PASS

    def test_empty_results_gives_pass(self, arbiter: ValidationArbiter):
        verdict = arbiter.decide(_context(), _report([]), [], True, 5.0)
        assert verdict.verdict == VerdictType.PASS


class TestArbiterCriticalFail:
    def test_critical_compliance_failure_gives_fail(self, arbiter: ValidationArbiter):
        results = [
            _check(True, SeverityLevel.LOW),
            _check(False, SeverityLevel.CRITICAL, "critical_rule"),
        ]
        verdict = arbiter.decide(_context(), _report(results), [], True, 10.0)
        assert verdict.verdict == VerdictType.FAIL
        assert any("[CRITICAL]" in r for r in verdict.recommendations)

    def test_critical_threat_high_confidence_gives_fail(self, arbiter: ValidationArbiter):
        threat = _threat(SeverityLevel.CRITICAL, confidence=0.9)
        verdict = arbiter.decide(_context(), _report([]), [threat], True, 10.0)
        assert verdict.verdict == VerdictType.FAIL
        assert any("[THREAT/CRITICAL]" in r for r in verdict.recommendations)

    def test_critical_threat_low_confidence_no_fail(self, arbiter: ValidationArbiter):
        """CRITICAL threat with confidence < 0.7 should NOT trigger FAIL."""
        threat = _threat(SeverityLevel.CRITICAL, confidence=0.5)
        verdict = arbiter.decide(_context(), _report([]), [threat], True, 10.0)
        assert verdict.verdict != VerdictType.FAIL


class TestArbiterConditionalPass:
    def test_high_compliance_failure_gives_conditional_pass(self, arbiter: ValidationArbiter):
        results = [_check(False, SeverityLevel.HIGH, "high_rule")]
        verdict = arbiter.decide(_context(), _report(results), [], True, 10.0)
        assert verdict.verdict == VerdictType.CONDITIONAL_PASS
        assert any("[HIGH]" in r for r in verdict.recommendations)

    def test_red_team_unavailable_gives_conditional_pass(self, arbiter: ValidationArbiter):
        verdict = arbiter.decide(_context(), _report([]), [], False, 10.0)
        assert verdict.verdict == VerdictType.CONDITIONAL_PASS
        assert any("Red Teaming agent was unavailable" in r for r in verdict.recommendations)

    def test_high_threat_with_enough_confidence(self, arbiter: ValidationArbiter):
        threat = _threat(SeverityLevel.HIGH, confidence=0.6)
        verdict = arbiter.decide(_context(), _report([]), [threat], True, 10.0)
        assert verdict.verdict == VerdictType.CONDITIONAL_PASS

    def test_high_threat_low_confidence_stays_pass(self, arbiter: ValidationArbiter):
        threat = _threat(SeverityLevel.HIGH, confidence=0.3)
        verdict = arbiter.decide(_context(), _report([]), [threat], True, 10.0)
        assert verdict.verdict == VerdictType.PASS


class TestArbiterPrecedence:
    def test_critical_overrides_high(self, arbiter: ValidationArbiter):
        results = [
            _check(False, SeverityLevel.HIGH),
            _check(False, SeverityLevel.CRITICAL),
        ]
        verdict = arbiter.decide(_context(), _report(results), [], True, 10.0)
        assert verdict.verdict == VerdictType.FAIL

    def test_critical_overrides_red_team_unavailable(self, arbiter: ValidationArbiter):
        results = [_check(False, SeverityLevel.CRITICAL)]
        verdict = arbiter.decide(_context(), _report(results), [], False, 10.0)
        assert verdict.verdict == VerdictType.FAIL

    def test_verdict_contains_correlation_id(self, arbiter: ValidationArbiter):
        ctx = _context()
        verdict = arbiter.decide(ctx, _report([]), [], True, 10.0)
        assert verdict.correlation_id == ctx.correlation_id
