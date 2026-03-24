from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import asyncpg

from mval.domain.enums import ValidationPhase
from mval.domain.models import PolicyRule, PolicyRuleCreate


class PolicyRepository:
    """БДвал access layer (PostgreSQL via asyncpg)."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    def _row_to_model(self, row: asyncpg.Record) -> PolicyRule:
        return PolicyRule(
            id=row["id"],
            name=row["name"],
            phase=row["phase"],
            category=row["category"],
            severity=row["severity"],
            rule_expression=row["rule_expression"],
            expected_value=row["expected_value"],
            description=row["description"],
            enabled=row["enabled"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def get_rules(self, phase: ValidationPhase) -> list[PolicyRule]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM policy_rules WHERE phase = $1 AND enabled = TRUE",
                phase.value,
            )
        return [self._row_to_model(r) for r in rows]

    async def get_rule(self, rule_id: UUID) -> PolicyRule | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM policy_rules WHERE id = $1", rule_id
            )
        return self._row_to_model(row) if row else None

    async def create_rule(self, rule: PolicyRuleCreate) -> PolicyRule:
        now = datetime.now(timezone.utc)
        rule_id = uuid4()
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO policy_rules
                    (id, name, phase, category, severity, rule_expression,
                     expected_value, description, enabled, created_at, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                """,
                rule_id,
                rule.name,
                rule.phase.value,
                rule.category.value,
                rule.severity.value,
                rule.rule_expression,
                rule.expected_value,
                rule.description,
                rule.enabled,
                now,
                now,
            )
        return PolicyRule(
            id=rule_id, **rule.model_dump(), created_at=now, updated_at=now
        )

    async def update_rule(
        self, rule_id: UUID, rule: PolicyRuleCreate
    ) -> PolicyRule | None:
        now = datetime.now(timezone.utc)
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE policy_rules SET
                    name=$2, phase=$3, category=$4, severity=$5,
                    rule_expression=$6, expected_value=$7,
                    description=$8, enabled=$9, updated_at=$10
                WHERE id=$1
                """,
                rule_id,
                rule.name,
                rule.phase.value,
                rule.category.value,
                rule.severity.value,
                rule.rule_expression,
                rule.expected_value,
                rule.description,
                rule.enabled,
                now,
            )
        if result == "UPDATE 0":
            return None
        return await self.get_rule(rule_id)

    async def delete_rule(self, rule_id: UUID) -> bool:
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM policy_rules WHERE id = $1", rule_id
            )
        return result != "DELETE 0"

    async def list_rules(self) -> list[PolicyRule]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM policy_rules ORDER BY created_at")
        return [self._row_to_model(r) for r in rows]
