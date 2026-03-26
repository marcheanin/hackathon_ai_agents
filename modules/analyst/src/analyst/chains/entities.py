from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from analyst.chains.llm_client import LLMClient
from analyst.config import LLM_MODE
from analyst.models.entities import ExtractedEntities, Integration, NFR


class EntityExtractionResult(BaseModel):
    entities: ExtractedEntities
    new_fields: list[str] = Field(default_factory=list)
    merge_strategy: Literal["append", "overwrite"] = "overwrite"


class _LLMEntityPayload(BaseModel):
    capabilities: list[str] = Field(default_factory=list)
    business_requirements: list[str] = Field(default_factory=list)
    system_name: str | None = None
    nfr: NFR | None = None
    integrations: list[Integration] = Field(default_factory=list)
    transfer_mode: str | None = None
    limit_or_amount_rules: str | None = None
    sms_confirm: bool | None = None
    aml_check_threshold: str | None = None
    auto_cancel_after_minutes: int | None = None
    pending_policy: str | None = None
    rollback_strategy: str | None = None


def _known_capabilities_hint() -> list[str]:
    path = Path(__file__).resolve().parents[1] / "data" / "agents.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    caps: set[str] = set()
    for row in payload:
        if isinstance(row, dict):
            for c in row.get("capabilities", []):
                if isinstance(c, str) and c:
                    caps.add(c)
    return sorted(caps)


def _entity_prompt() -> str:
    path = Path(__file__).resolve().parents[1] / "prompts" / "entity_extractor.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return (
            "Extract product entities. Return JSON only with fields: capabilities, business_requirements, system_name, "
            "nfr, integrations, transfer_mode, limit_or_amount_rules, sms_confirm, aml_check_threshold, "
            "auto_cancel_after_minutes, pending_policy, rollback_strategy."
        )


def _entity_user_prompt(user_message: str, conversation_history: list[dict[str, Any]] | None) -> str:
    parts = [f"user_message:\n{user_message.strip()}"]
    if conversation_history:
        tail = conversation_history[-10:]
        parts.append(f"conversation_history_tail:\n{tail}")
    known_caps = _known_capabilities_hint()
    if known_caps:
        parts.append(f"known_capabilities:\n{known_caps}")
    return "\n\n".join(parts)


def _extract_number(patterns: list[str], text: str) -> int | None:
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                continue
    return None


def _extract_amount_rub(text: str) -> int | None:
    """Объём/лимит: `до 100к руб`, `до 100000 руб`, или «100 тыс» для квот тикетов."""
    m_k = re.search(r"до\s*([0-9]+)\s*[кK]\b", text, flags=re.IGNORECASE)
    if m_k:
        return int(m_k.group(1)) * 1000
    m_rub = re.search(r"до\s*([0-9]+)\s*руб", text, flags=re.IGNORECASE)
    if m_rub:
        return int(m_rub.group(1))
    m_ty = re.search(r"([0-9]+)\s*тыс", text, flags=re.IGNORECASE)
    if m_ty:
        return int(m_ty.group(1)) * 1000
    return None


def _heuristic_extract_entities(
    *,
    user_message: str,
    conversation_history: list[dict[str, Any]] | None = None,
    existing_entities: ExtractedEntities | None = None,
) -> EntityExtractionResult:
    text = user_message
    lower = text.lower()

    capabilities: list[str] = []

    # Портал поддержки банков-клиентов
    if any(
        k in lower
        for k in (
            "тикет",
            "заявк",
            "техподдерж",
            "support request",
            "support ticket",
            "service desk",
            "банк-клиент",
            "банков-клиент",
            "портал поддержки",
            "обращени",
            "клиент банка",
            "sla",
        )
    ):
        capabilities += ["client_ticket_ingest", "bank_sla_tracking", "escalation_workflow"]
    if "webhook" in lower or re.search(r"\brest\b", lower) or "rest api" in lower:
        capabilities += ["webhook_ingestion"]

    if "sms" in lower or "смс" in lower:
        capabilities += ["sms_sending", "sms_confirm"]

    amount_rub = _extract_amount_rub(text)

    # Документация / wiki
    if any(k in lower for k in ("confluence", "документац", "wiki", "регламент", "kb ", "knowledge base")):
        capabilities += ["documentation_search", "wiki_index", "doc_versioning"]

    # Реестр продуктов и версий
    if any(k in lower for k in ("semver", "реестр продукт", "product registry", "верси продукт", "релизн поезд")):
        capabilities += ["product_line_registry", "semver_matrix", "release_train_mapping"]

    # Уязвимости / SBOM (поле aml_check_threshold переиспользуем как порог severity)
    if any(k in lower for k in ("cve", "cvss", "уязвим", "sbom", "зависимост", "supply chain")):
        capabilities += ["vulnerability_scan", "sbom_validation", "dependency_audit"]
    if amount_rub is not None and amount_rub >= 15000 and "vulnerability_scan" in capabilities:
        pass  # порог ниже по CVSS

    if "лимит" in lower:
        capabilities += ["limit_enforcement"]
    if re.search(r"до\s*100\s*к\b", lower, flags=re.IGNORECASE):
        capabilities += ["limit_enforcement"]

    # Git / MR
    if any(
        k in lower
        for k in (
            "git",
            "гит",
            "коммит",
            "commit",
            "merge request",
            "репозитор",
            "ветк",
            "branch protection",
            "исправлени кода",
            "редактировани кода",
            "bugfix",
            "fix bug",
            "исправлени баг",
        )
    ) or re.search(
        r"\bmr\b", lower
    ):
        capabilities += ["repository_lifecycle", "merge_request_policy", "branch_protection", "signed_commits"]

    # CI/CD
    if any(k in lower for k in ("ci/cd", "ci ", "cd ", "пайплайн", "сборк", "деплой", "deployment gate")):
        capabilities += ["pipeline_template_library", "build_artifact_signing", "deployment_gate"]

    # Внутренний task tracker
    if any(k in lower for k in ("jira", "youtrack", "трекер задач", "task tracker", "спринт", "work item")):
        capabilities += ["work_item_sync", "sprint_velocity_export", "cross_tool_linking"]

    # Договоры с банком
    if any(k in lower for k in ("договор", "контракт", "соглашени", "amendment")):
        capabilities += ["contract_clause_extract", "amendment_diff", "regulatory_mapping"]

    # Артефактный реестр / npm mirror
    if any(k in lower for k in ("artifact", "артефакт", "npm mirror", "binary registry", "пакетн регистр")):
        capabilities += ["binary_package_registry", "promotion_workflow"]

    # Observability
    if any(k in lower for k in ("service catalog", "slo ", "runbook", "observability")):
        capabilities += ["service_catalog_export", "slo_burn_alert", "runbook_linking"]

    # NFR
    rps = _extract_number([r"rps\s*([0-9]+)", r"RPS\s*([0-9]+)"], text)
    peak_rps = _extract_number([r"пик\s*([0-9]+)", r"peak\s*([0-9]+)"], text)
    m_lat_sec = re.search(r"задержк\w*\s*до\s*([0-9]+)\s*сек", text, flags=re.IGNORECASE)
    m_lat_ms = re.search(r"задержк\w*\s*до\s*([0-9]+)\s*(мс|ms)", text, flags=re.IGNORECASE)
    latency = _extract_number([r"latency\s*до\s*([0-9]+)", r"p99\s*([0-9]+)"], text)
    if m_lat_sec:
        latency = int(m_lat_sec.group(1)) * 1000
    elif m_lat_ms:
        latency = int(m_lat_ms.group(1))

    nfr = NFR(
        rps=rps,
        peak_rps=peak_rps,
        latency_p99_ms=latency,
        sla_percent=None,
        idempotency=None,
    )

    transfer_mode = None
    if "со счёта на счёт" in lower or "с счета на счет" in lower or "со счета на счет" in lower:
        transfer_mode = "account_to_account"
    elif "с карты" in lower:
        transfer_mode = "account_to_card"
    elif "webhook" in lower:
        transfer_mode = "rest_webhook_ingest"
    elif re.search(r"\brest\b", lower) or "rest api" in lower:
        transfer_mode = "rest_api_ingest"

    sms_confirm = True if ("sms" in lower or "смс" in lower or "подтверж" in lower) else None

    limit_or_amount_rules = f"до {amount_rub} руб" if amount_rub is not None else None

    aml_check_threshold = None
    m_cvss = re.search(r"cvss\s*[>=]*\s*([0-9]+(?:\.[0-9]+)?)", text, flags=re.IGNORECASE)
    if m_cvss:
        aml_check_threshold = f"CVSS>={m_cvss.group(1)}"
    elif "vulnerability_scan" in capabilities and amount_rub is not None and amount_rub >= 15000:
        aml_check_threshold = ">=15000_volume_gate"

    auto_cancel_after_minutes = None
    m_cancel = re.search(r"через\s*([0-9]+)\s*минут", text, flags=re.IGNORECASE)
    if m_cancel:
        try:
            auto_cancel_after_minutes = int(m_cancel.group(1))
        except ValueError:
            auto_cancel_after_minutes = None

    pending_policy = "pending" if "pending" in lower else None
    rollback_strategy = None
    if auto_cancel_after_minutes is not None:
        rollback_strategy = "auto_cancel"
    elif pending_policy is not None:
        rollback_strategy = "pending"
    elif "откат" in lower or "rollback" in lower:
        rollback_strategy = "release_rollback"

    business_requirements: list[str] = []
    if text.strip():
        business_requirements.append(text.strip())

    system_name = None
    m = re.search(r"(?:сервис|портал|система)\s+([A-Za-zА-Яа-я0-9_\- ]+)", user_message, flags=re.IGNORECASE)
    if m:
        system_name = m.group(1).strip()

    constraints = None
    integrations: list[Integration] = []

    merge_strategy: Literal["append", "overwrite"] = "overwrite"
    if existing_entities is not None:
        existing_caps = set(existing_entities.capabilities or [])
        new_caps = set(capabilities or [])
        if existing_caps:
            merge_strategy = "append" if not existing_caps.isdisjoint(new_caps) else "overwrite"
        else:
            merge_strategy = "append" if existing_entities.business_requirements else "overwrite"

    entities = ExtractedEntities(
        intent=None,
        capabilities=sorted(set(capabilities)),
        business_requirements=business_requirements,
        system_name=system_name,
        nfr=nfr if any(v is not None for v in nfr.model_dump().values()) else None,
        integrations=integrations,
        constraints=constraints,
        technologies=[],
        features=[],
        limit=None,
        transfer_mode=transfer_mode,
        limit_or_amount_rules=limit_or_amount_rules,
        sms_confirm=sms_confirm,
        aml_check_threshold=aml_check_threshold,
        auto_cancel_after_minutes=auto_cancel_after_minutes,
        pending_policy=pending_policy,
        rollback_strategy=rollback_strategy,
    )

    return EntityExtractionResult(entities=entities, new_fields=list(entities.model_dump().keys()), merge_strategy=merge_strategy)


async def extract_entities(
    *,
    user_message: str,
    conversation_history: list[dict[str, Any]] | None = None,
    existing_entities: ExtractedEntities | None = None,
    domain_hint: str | None = None,
) -> EntityExtractionResult:
    if LLM_MODE == "mock":
        return _heuristic_extract_entities(
            user_message=user_message,
            conversation_history=conversation_history,
            existing_entities=existing_entities,
        )

    # live path: try LLM extraction first, then deterministic fallback
    try:
        payload = await LLMClient().call_structured(
            system_prompt=_entity_prompt(),
            user_prompt=_entity_user_prompt(user_message, conversation_history),
            response_model=_LLMEntityPayload,
        )
        assert isinstance(payload, _LLMEntityPayload)
        incoming = ExtractedEntities(
            intent=None,
            capabilities=sorted(set(payload.capabilities or [])),
            business_requirements=list(payload.business_requirements or []) or ([user_message.strip()] if user_message.strip() else []),
            system_name=payload.system_name,
            nfr=payload.nfr,
            integrations=payload.integrations or [],
            constraints=None,
            technologies=[],
            features=[],
            limit=None,
            transfer_mode=payload.transfer_mode,
            limit_or_amount_rules=payload.limit_or_amount_rules,
            sms_confirm=payload.sms_confirm,
            aml_check_threshold=payload.aml_check_threshold,
            auto_cancel_after_minutes=payload.auto_cancel_after_minutes,
            pending_policy=payload.pending_policy,
            rollback_strategy=payload.rollback_strategy,
        )
        merge_strategy: Literal["append", "overwrite"] = "overwrite"
        if existing_entities is not None:
            existing_caps = set(existing_entities.capabilities or [])
            new_caps = set(incoming.capabilities or [])
            if existing_caps:
                merge_strategy = "append" if not existing_caps.isdisjoint(new_caps) else "overwrite"
            else:
                merge_strategy = "append" if existing_entities.business_requirements else "overwrite"
        return EntityExtractionResult(
            entities=incoming,
            new_fields=list(incoming.model_dump().keys()),
            merge_strategy=merge_strategy,
        )
    except Exception:
        return _heuristic_extract_entities(
            user_message=user_message,
            conversation_history=conversation_history,
            existing_entities=existing_entities,
        )
