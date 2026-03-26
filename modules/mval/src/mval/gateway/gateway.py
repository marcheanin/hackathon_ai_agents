from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import structlog

from mval.domain.enums import ValidationPhase
from mval.domain.models import ValidationContext, ValidationVerdict
from mval.logging.audit import AuditLogger
from mval.validators.architecture_validator import ArchitectureValidator
from mval.validators.request_validator import RequestValidator

logger = structlog.get_logger("mval.gateway")

_LOG_DIR = Path(os.getenv("LLM_LOG_DIR", "/tmp/agent_logs"))
_LOG_DIR.mkdir(parents=True, exist_ok=True)


def _log_mval(phase: str, artifact: dict, verdict) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(_LOG_DIR / "mval.log", "a", encoding="utf-8") as f:
        f.write(f"\n{'='*80}\n[{ts}] МВАЛ :: validate ({phase})\n{'='*80}\n\n")
        f.write("--- INPUT ARTIFACT ---\n")
        f.write(f"{json.dumps(artifact, ensure_ascii=False, indent=2)[:3000]}\n\n")
        f.write("--- VERDICT ---\n")
        f.write(f"{verdict.model_dump_json(indent=2)[:3000]}\n\n")


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
            verdict = await self._request_validator.validate(context)
        elif context.phase == ValidationPhase.ARCHITECTURE:
            verdict = await self._architecture_validator.validate(context)
        else:
            raise ValueError(f"Unknown validation phase: {context.phase}")

        _log_mval(str(context.phase), context.artifact, verdict)
        return verdict

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
