from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from analyst.models.enums import IntentType


class NFR(BaseModel):
    """Non-functional requirements (MVP набор полей)."""

    rps: int | None = None
    peak_rps: int | None = None
    sla_percent: float | None = None
    latency_p99_ms: int | None = None
    idempotency: str | None = None


class Integration(BaseModel):
    name: str
    type: str | None = None
    auth: str | None = None
    purpose: str | None = None


class InfrastructureConstraints(BaseModel):
    cluster: str | None = None
    database: str | None = None
    messaging: str | None = None


class Constraints(BaseModel):
    security: list[str] = Field(default_factory=list)
    infrastructure: InfrastructureConstraints | dict[str, Any] | None = None


class DomainInfo(BaseModel):
    domain: str
    sub_domain: str | None = None
    confidence: float | None = None


class ExtractedEntities(BaseModel):
    """Накопленные сущности, извлеченные из запроса клиента."""

    intent: IntentType | None = None

    # Для Agent Match Evaluator
    capabilities: list[str] = Field(default_factory=list)

    # Для Sufficiency Evaluator / Synthesis
    business_requirements: list[str] = Field(default_factory=list)
    system_name: str | None = None

    # NFR & интеграции
    nfr: NFR | None = None
    integrations: list[Integration] = Field(default_factory=list)

    # Ограничения
    constraints: Constraints | None = None

    # Дополнительные “сырые” признаки (иногда удобны для доменного детектора)
    technologies: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    limit: str | None = None

    # Поля, которые используются в чек-листе достаточности (связаны с docs/checklist_templates.json)
    transfer_mode: str | None = None  # например: "account_to_account" / "account_to_card"
    limit_or_amount_rules: str | None = None
    sms_confirm: bool | None = None
    aml_check_threshold: str | None = None
    auto_cancel_after_minutes: int | None = None
    pending_policy: str | None = None
    rollback_strategy: str | None = None

