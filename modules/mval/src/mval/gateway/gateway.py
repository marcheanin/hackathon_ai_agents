from __future__ import annotations

import structlog

from mval.domain.enums import ValidationPhase
from mval.domain.models import ValidationContext, ValidationVerdict
from mval.logging.audit import AuditLogger
from mval.validators.architecture_validator import ArchitectureValidator
from mval.validators.request_validator import RequestValidator

logger = structlog.get_logger("mval.gateway")


class ValidationGateway:
    """Routes validation requests to the appropriate validator by phase."""

    def __init__(
        self,
        request_validator: RequestValidator,
        architecture_validator: ArchitectureValidator,
        audit: AuditLogger,
    ) -> None:
        self._request_validator = request_validator
        self._architecture_validator = architecture_validator
        self._audit = audit

    async def validate(self, context: ValidationContext) -> ValidationVerdict:
        self._audit.log_request(context)

        if context.phase == ValidationPhase.REQUEST:
            return await self._request_validator.validate(context)
        elif context.phase == ValidationPhase.ARCHITECTURE:
            return await self._architecture_validator.validate(context)
        else:
            raise ValueError(f"Unknown validation phase: {context.phase}")

    async def health(self) -> dict:
        return {
            "status": "ok",
            "module": "МВАЛ",
            "components": {
                "gateway": "ok",
                "request_validator": "ok",
                "architecture_validator": "ok",
            },
        }
