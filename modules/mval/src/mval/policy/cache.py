from __future__ import annotations

import json

import redis.asyncio as redis

from mval.domain.enums import ValidationPhase
from mval.domain.models import PolicyRule


class PolicyCache:
    """Redis-based policy cache with TTL."""

    KEY_PREFIX = "mval:policies:"

    def __init__(self, client: redis.Redis, ttl_seconds: int = 300) -> None:
        self._client = client
        self._ttl = ttl_seconds

    def _key(self, phase: ValidationPhase) -> str:
        return f"{self.KEY_PREFIX}{phase.value}"

    async def get_rules(self, phase: ValidationPhase) -> list[PolicyRule] | None:
        """Return cached rules or None on miss / error."""
        try:
            data = await self._client.get(self._key(phase))
        except Exception:
            return None
        if data is None:
            return None
        items = json.loads(data)
        return [PolicyRule.model_validate(item) for item in items]

    async def set_rules(self, phase: ValidationPhase, rules: list[PolicyRule]) -> None:
        """Cache rules with TTL. Silently ignores errors."""
        try:
            payload = json.dumps([r.model_dump(mode="json") for r in rules])
            await self._client.setex(self._key(phase), self._ttl, payload)
        except Exception:
            pass

    async def invalidate(self, phase: ValidationPhase | None = None) -> None:
        """Invalidate cache for a phase, or all phases."""
        try:
            if phase:
                await self._client.delete(self._key(phase))
            else:
                for p in ValidationPhase:
                    await self._client.delete(self._key(p))
        except Exception:
            pass
