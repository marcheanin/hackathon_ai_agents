"""Tests for RequestValidator — policy-only validation of request artifacts."""
from __future__ import annotations

import pytest

from mval.domain.enums import SeverityLevel, ValidationPhase, VerdictType
from mval.domain.models import ValidationContext
from mval.policy.circuit_breaker import CircuitBreaker
from mval.policy.engine import PolicyEngine
from mval.validators.request_validator import RequestValidator


class TestRequestValidatorValid:
    """Valid request artifact should produce PASS."""

    async def test_valid_request_passes(
        self, request_validator, fake_repo, request_rules, valid_request_context
    ):
        for rule in request_rules:
            fake_repo.seed(rule)

        verdict = await request_validator.validate(valid_request_context)
        assert verdict.verdict == VerdictType.PASS
        assert verdict.compliance_report.failed_count == 0

    async def test_verdict_has_correlation_id(
        self, request_validator, fake_repo, request_rules, valid_request_context
    ):
        for rule in request_rules:
            fake_repo.seed(rule)

        verdict = await request_validator.validate(valid_request_context)
        assert verdict.correlation_id == valid_request_context.correlation_id

    async def test_verdict_has_duration(
        self, request_validator, fake_repo, request_rules, valid_request_context
    ):
        for rule in request_rules:
            fake_repo.seed(rule)

        verdict = await request_validator.validate(valid_request_context)
        assert verdict.duration_ms >= 0


class TestRequestValidatorMissingField:
    """Missing required field should produce FAIL (CRITICAL severity)."""

    async def test_missing_objective_fails(
        self, request_validator, fake_repo, request_rules, invalid_request_context
    ):
        for rule in request_rules:
            fake_repo.seed(rule)

        verdict = await request_validator.validate(invalid_request_context)
        assert verdict.verdict == VerdictType.FAIL
        assert verdict.compliance_report.failed_count > 0

    async def test_missing_objective_has_critical_severity(
        self, request_validator, fake_repo, request_rules, invalid_request_context
    ):
        for rule in request_rules:
            fake_repo.seed(rule)

        verdict = await request_validator.validate(invalid_request_context)
        assert verdict.compliance_report.highest_severity == SeverityLevel.CRITICAL


class TestRequestValidatorInjection:
    """Injection pattern in objective should produce FAIL."""

    async def test_injection_detected(
        self, request_validator, fake_repo, request_rules, injection_request_context
    ):
        for rule in request_rules:
            fake_repo.seed(rule)

        verdict = await request_validator.validate(injection_request_context)
        assert verdict.verdict == VerdictType.FAIL

    async def test_injection_recommendation(
        self, request_validator, fake_repo, request_rules, injection_request_context
    ):
        for rule in request_rules:
            fake_repo.seed(rule)

        verdict = await request_validator.validate(injection_request_context)
        assert len(verdict.recommendations) > 0
        assert any("CRITICAL" in r for r in verdict.recommendations)


class TestRequestValidatorFailClosed:
    """When PolicyEngine is unavailable, validation should fail-closed."""

    async def test_policy_engine_failure_gives_fail(
        self, arbiter, fake_audit, fake_cache
    ):
        class FailingRepo:
            async def get_rules(self, phase):
                raise ConnectionError("DB down")

        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=999)
        engine = PolicyEngine(FailingRepo(), fake_cache, cb)
        validator = RequestValidator(engine, arbiter, fake_audit)

        ctx = ValidationContext(
            phase=ValidationPhase.REQUEST,
            source_module="MAN",
            target_module="MVAL",
            artifact={"objective": "test"},
        )

        verdict = await validator.validate(ctx)
        assert verdict.verdict == VerdictType.FAIL
        assert any("unavailable" in r.lower() for r in verdict.recommendations)

    async def test_policy_engine_failure_logs_error(
        self, arbiter, fake_audit, fake_cache
    ):
        class FailingRepo:
            async def get_rules(self, phase):
                raise ConnectionError("DB down")

        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=999)
        engine = PolicyEngine(FailingRepo(), fake_cache, cb)
        validator = RequestValidator(engine, arbiter, fake_audit)

        ctx = ValidationContext(
            phase=ValidationPhase.REQUEST,
            source_module="MAN",
            target_module="MVAL",
            artifact={"objective": "test"},
        )

        await validator.validate(ctx)
        assert len(fake_audit.errors) > 0
        assert fake_audit.errors[0]["error"] == "policy_engine_unavailable"


class TestRequestValidatorAuditLogging:
    """Successful validation should log the verdict via AuditLogger."""

    async def test_successful_validation_logs_verdict(
        self, request_validator, fake_repo, fake_audit, request_rules, valid_request_context
    ):
        for rule in request_rules:
            fake_repo.seed(rule)

        await request_validator.validate(valid_request_context)
        assert len(fake_audit.verdicts) == 1
        assert fake_audit.verdicts[0].verdict == VerdictType.PASS
