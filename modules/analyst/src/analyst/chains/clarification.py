from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from analyst.chains.llm_client import LLMClient
from analyst.config import LLM_MODE
from analyst.models.context import EnrichedContext


class ClarificationResult(BaseModel):
    questions: list[str] = Field(default_factory=list)
    target_gaps: list[str] = Field(default_factory=list)
    expected_impact: int = Field(default=10, ge=0, le=100)


class _LLMClarificationPayload(BaseModel):
    questions: list[str] = Field(default_factory=list)
    target_gaps: list[str] = Field(default_factory=list)
    expected_impact: int = Field(default=20, ge=0, le=100)


def _prompt_text() -> str:
    path = Path(__file__).resolve().parents[1] / "prompts" / "clarification_generator.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return "Generate up to 3 clarification questions, JSON only."


_GAP_TO_QUESTION: dict[str, str] = {
    "system_name": "Как назвать целевую систему (например: Bank Client Support Portal)?",
    "business_requirements": "Какие ключевые бизнес-требования обязательны (каналы от банка, роли, процессы)?",
    "nfr_rps_latency": "Укажите нагрузку и SLA: `RPS`, `peak RPS`, `p99 latency` (и SLA % при наличии).",
    "bank_integration_channel": "Как банк передаёт обращения: REST webhook, портал, файлы? Какие лимиты/квоты?",
    "status_notification": "Нужны ли уведомления банку о статусе (SMS/e-mail), шаблоны и таймауты?",
    "supply_chain_gate": "Какие требования к CVE/SBOM для поставляемых артефактов (порог CVSS, обязательный SBOM)?",
    "auto_escalation_policy": "Что делать при отсутствии ответа: эскалация через N минут, auto-close или pending?",
    "rollback_strategy": "Какая стратегия отката релиза/конфигурации при сбое?",
    "account_source_target": "Уточните канал интеграции и лимиты (legacy-поле чек-листа).",
    "sms_confirmation": "Нужно ли подтверждение статуса по SMS и с каким SLA?",
    "aml_check": "Уточните пороги compliance/сканирования (legacy).",
    "auto_cancel_policy": "Политика при отсутствии подтверждения (legacy).",
    "no_checklist_template_found": "Уточните домен (client_delivery/support_portal, engineering_platform/git, …) и ключевые требования.",
}


async def generate_clarification(
    *,
    gaps: list[str],
    conversation_history: list[dict[str, Any]] | None = None,
    already_asked: list[str] | None = None,
    enriched_context: EnrichedContext | None = None,
) -> ClarificationResult:
    if LLM_MODE != "mock":
        try:
            payload = await LLMClient().call_structured(
                system_prompt=_prompt_text(),
                user_prompt=(
                    f"gaps: {gaps}\n"
                    f"already_asked: {already_asked or []}\n"
                    f"conversation_tail: {(conversation_history or [])[-8:]}\n"
                    f"matched_agents: {[m.model_dump() for m in (enriched_context.agent_matches if enriched_context else [])[:6]]}\n"
                    f"available_tools: {(enriched_context.tool_list if enriched_context else [])}\n"
                    f"dynamic_requirements: {[r.model_dump() for r in (enriched_context.dynamic_requirements if enriched_context else [])]}\n"
                ),
                response_model=_LLMClarificationPayload,
            )
            assert isinstance(payload, _LLMClarificationPayload)
            return ClarificationResult(
                questions=payload.questions[:3],
                target_gaps=payload.target_gaps[:3] or gaps[:3],
                expected_impact=payload.expected_impact,
            )
        except Exception:
            pass

    already_asked = already_asked or []
    selected: list[str] = []

    for g in gaps:
        if g in already_asked:
            continue
        selected.append(g)
        if len(selected) >= 3:
            break

    # Fallback: если не нашли сопоставлений, зададим общий вопрос
    if not selected and gaps:
        selected = [gaps[0]]

    questions: list[str] = []
    for g in selected:
        if g in _GAP_TO_QUESTION:
            questions.append(_GAP_TO_QUESTION[g])
            continue
        # deterministic fallback for unknown dynamic gaps
        dyn_req_desc = None
        if enriched_context is not None:
            for req in enriched_context.dynamic_requirements:
                if req.id == g:
                    dyn_req_desc = req.description
                    break
        questions.append(dyn_req_desc or f"Уточните пункт: {g}")

    expected_impact = 40 if any("nfr" in q.lower() for q in questions) else 20
    return ClarificationResult(questions=questions, target_gaps=selected, expected_impact=expected_impact)

