"""Tests for ValidationGateway — routing and health."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from mval.domain.enums import ValidationPhase, VerdictType
from mval.domain.models import (
    ComplianceReport,
    ValidationContext,
    ValidationVerdict,
)
from mval.gateway.gateway import ValidationGateway


def _make_verdict(ctx: ValidationContext, verdict_type: VerdictType) -> ValidationVerdict:
    return ValidationVerdict(
        correlation_id=ctx.correlation_id,
        phase=ctx.phase,
        verdict=verdict_type,
        compliance_report=ComplianceReport(phase=ctx.phase),
        duration_ms=5.0,
    )


class TestGatewayRouting:
    """Gateway should route to the correct validator based on phase."""

    async def test_request_phase_routes_to_request_validator(self, fake_audit):
        req_validator = AsyncMock()
        arch_validator = AsyncMock()

        ctx = ValidationContext(
            phase=ValidationPhase.REQUEST,
            source_module="MAN",
            target_module="MVAL",
            artifact={"objective": "test"},
        )
        expected = _make_verdict(ctx, VerdictType.PASS)
        req_validator.validate.return_value = expected

        gateway = ValidationGateway(req_validator, arch_validator, fake_audit)
        result = await gateway.validate(ctx)

        req_validator.validate.assert_called_once_with(ctx)
        arch_validator.validate.assert_not_called()
        assert result.verdict == VerdictType.PASS

    async def test_architecture_phase_routes_to_architecture_validator(self, fake_audit):
        req_validator = AsyncMock()
        arch_validator = AsyncMock()

        ctx = ValidationContext(
            phase=ValidationPhase.ARCHITECTURE,
            source_module="MARX",
            target_module="MVAL",
            artifact={"components": []},
        )
        expected = _make_verdict(ctx, VerdictType.CONDITIONAL_PASS)
        arch_validator.validate.return_value = expected

        gateway = ValidationGateway(req_validator, arch_validator, fake_audit)
        result = await gateway.validate(ctx)

        arch_validator.validate.assert_called_once_with(ctx)
        req_validator.validate.assert_not_called()
        assert result.verdict == VerdictType.CONDITIONAL_PASS

    async def test_gateway_logs_request(self, fake_audit):
        req_validator = AsyncMock()
        arch_validator = AsyncMock()

        ctx = ValidationContext(
            phase=ValidationPhase.REQUEST,
            source_module="MAN",
            target_module="MVAL",
            artifact={"objective": "test"},
        )
        req_validator.validate.return_value = _make_verdict(ctx, VerdictType.PASS)

        gateway = ValidationGateway(req_validator, arch_validator, fake_audit)
        await gateway.validate(ctx)

        assert len(fake_audit.requests) == 1
        assert fake_audit.requests[0].correlation_id == ctx.correlation_id


class TestGatewayHealth:
    """Health endpoint should return ok status."""

    async def test_health_returns_ok(self, fake_audit):
        req_validator = AsyncMock()
        arch_validator = AsyncMock()

        gateway = ValidationGateway(req_validator, arch_validator, fake_audit)
        result = await gateway.health()

        assert result["status"] == "ok"
        assert result["module"] == "МВАЛ"
        assert "gateway" in result["components"]
        assert result["components"]["gateway"] == "ok"
