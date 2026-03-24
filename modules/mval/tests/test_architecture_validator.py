"""Tests for ArchitectureValidator — policy + red team sidecar validation."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from mval.domain.enums import (
    PolicyCategory,
    SeverityLevel,
    ValidationPhase,
    VerdictType,
)
from mval.domain.models import PolicyRule, ValidationContext
from mval.policy.circuit_breaker import CircuitBreaker
from mval.policy.engine import PolicyEngine
from mval.validators.architecture_validator import ArchitectureValidator


def _arch_context(artifact: dict | None = None) -> ValidationContext:
    return ValidationContext(
        phase=ValidationPhase.ARCHITECTURE,
        source_module="MARX",
        target_module="MVAL",
        artifact=artifact or {
            "components": [
                {"name": "agent-1", "type": "llm", "config": {"model": "gpt-4"}},
            ],
            "connections": [],
        },
    )


def _mock_httpx_client(post_return=None, post_side_effect=None):
    """Create a mock httpx.AsyncClient context manager."""
    mock_client = AsyncMock()
    if post_return is not None:
        mock_client.post.return_value = post_return
    if post_side_effect is not None:
        mock_client.post.side_effect = post_side_effect
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def _mock_response(findings=None, error=None):
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "findings": findings or [],
        "error": error,
    }
    return resp


class TestArchitectureValidatorPass:
    """Valid architecture with successful red team should PASS."""

    async def test_valid_architecture_passes(
        self, architecture_validator, fake_repo, architecture_rules, valid_architecture_context
    ):
        for rule in architecture_rules:
            fake_repo.seed(rule)

        mock_client = _mock_httpx_client(post_return=_mock_response())

        with patch("mval.validators.architecture_validator.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = mock_client

            verdict = await architecture_validator.validate(valid_architecture_context)

        assert verdict.verdict == VerdictType.PASS
        assert verdict.red_team_available is True
        assert verdict.compliance_report.failed_count == 0


class TestArchitectureValidatorRedTeamTimeout:
    """Red team timeout should produce CONDITIONAL_PASS."""

    async def test_red_team_timeout_gives_conditional_pass(
        self, architecture_validator, fake_repo, architecture_rules, valid_architecture_context
    ):
        for rule in architecture_rules:
            fake_repo.seed(rule)

        mock_client = _mock_httpx_client(
            post_side_effect=httpx.TimeoutException("timeout")
        )

        with patch("mval.validators.architecture_validator.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = mock_client

            verdict = await architecture_validator.validate(valid_architecture_context)

        assert verdict.verdict == VerdictType.CONDITIONAL_PASS
        assert verdict.red_team_available is False
        assert any("Red Teaming agent was unavailable" in r for r in verdict.recommendations)

    async def test_red_team_connect_error_gives_conditional_pass(
        self, architecture_validator, fake_repo, architecture_rules, valid_architecture_context
    ):
        for rule in architecture_rules:
            fake_repo.seed(rule)

        mock_client = _mock_httpx_client(
            post_side_effect=httpx.ConnectError("connection refused")
        )

        with patch("mval.validators.architecture_validator.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = mock_client

            verdict = await architecture_validator.validate(valid_architecture_context)

        assert verdict.verdict == VerdictType.CONDITIONAL_PASS
        assert verdict.red_team_available is False


class TestArchitectureValidatorRedTeamError:
    """Red team returning error field should mark unavailable."""

    async def test_redteam_error_response(
        self, architecture_validator, fake_repo, architecture_rules, valid_architecture_context
    ):
        for rule in architecture_rules:
            fake_repo.seed(rule)

        mock_client = _mock_httpx_client(
            post_return=_mock_response(error="LLM unavailable")
        )

        with patch("mval.validators.architecture_validator.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = mock_client

            verdict = await architecture_validator.validate(valid_architecture_context)

        assert verdict.red_team_available is False
        assert verdict.verdict == VerdictType.CONDITIONAL_PASS


class TestArchitectureValidatorPolicyFailure:
    """Policy engine failure should produce FAIL (fail-closed)."""

    async def test_policy_engine_failure_gives_fail(self, arbiter, fake_audit, fake_cache):
        class FailingRepo:
            async def get_rules(self, phase):
                raise ConnectionError("DB down")

        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=999)
        engine = PolicyEngine(FailingRepo(), fake_cache, cb)
        validator = ArchitectureValidator(
            policy_engine=engine,
            arbiter=arbiter,
            audit=fake_audit,
            redteam_url="http://fake:8001",
            redteam_timeout=5,
        )

        mock_client = _mock_httpx_client(post_return=_mock_response())

        with patch("mval.validators.architecture_validator.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = mock_client

            ctx = _arch_context()
            verdict = await validator.validate(ctx)

        assert verdict.verdict == VerdictType.FAIL
        assert any("unavailable" in r.lower() for r in verdict.recommendations)

    async def test_policy_engine_failure_logs_error(self, arbiter, fake_audit, fake_cache):
        class FailingRepo:
            async def get_rules(self, phase):
                raise ConnectionError("DB down")

        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=999)
        engine = PolicyEngine(FailingRepo(), fake_cache, cb)
        validator = ArchitectureValidator(
            policy_engine=engine,
            arbiter=arbiter,
            audit=fake_audit,
            redteam_url="http://fake:8001",
            redteam_timeout=5,
        )

        mock_client = _mock_httpx_client(
            post_side_effect=httpx.ConnectError("refused")
        )

        with patch("mval.validators.architecture_validator.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = mock_client

            ctx = _arch_context()
            await validator.validate(ctx)

        assert len(fake_audit.errors) > 0


class TestArchitectureValidatorWithFindings:
    """Red team returning threat findings should affect verdict."""

    async def test_critical_threat_finding_gives_fail(
        self, architecture_validator, fake_repo, architecture_rules, valid_architecture_context
    ):
        for rule in architecture_rules:
            fake_repo.seed(rule)

        findings_data = [
            {
                "finding_id": str(uuid4()),
                "threat_name": "SQL Injection",
                "description": "Possible SQL injection vector",
                "severity": "CRITICAL",
                "attack_vector": "user input",
                "mitigation": "Use parameterized queries",
                "confidence": 0.9,
            }
        ]

        mock_client = _mock_httpx_client(
            post_return=_mock_response(findings=findings_data)
        )

        with patch("mval.validators.architecture_validator.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = mock_client

            verdict = await architecture_validator.validate(valid_architecture_context)

        assert verdict.verdict == VerdictType.FAIL
        assert len(verdict.threat_findings) == 1
        assert verdict.red_team_available is True

    async def test_high_threat_finding_gives_conditional_pass(
        self, architecture_validator, fake_repo, architecture_rules, valid_architecture_context
    ):
        for rule in architecture_rules:
            fake_repo.seed(rule)

        findings_data = [
            {
                "finding_id": str(uuid4()),
                "threat_name": "Weak Auth",
                "description": "Weak authentication mechanism",
                "severity": "HIGH",
                "attack_vector": "brute force",
                "mitigation": "Use MFA",
                "confidence": 0.7,
            }
        ]

        mock_client = _mock_httpx_client(
            post_return=_mock_response(findings=findings_data)
        )

        with patch("mval.validators.architecture_validator.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = mock_client

            verdict = await architecture_validator.validate(valid_architecture_context)

        assert verdict.verdict == VerdictType.CONDITIONAL_PASS
        assert len(verdict.threat_findings) == 1
