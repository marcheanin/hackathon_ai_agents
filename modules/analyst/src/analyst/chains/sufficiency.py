from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from analyst.chains.llm_client import LLMClient
from analyst.config import LLM_MODE
from analyst.models.context import DynamicRequirement, EnrichedContext
from analyst.models.entities import DomainInfo, ExtractedEntities


class SufficiencyEvaluationResult(BaseModel):
    score: int = Field(ge=0, le=100)
    gaps: list[str] = Field(default_factory=list)
    checklist_results: list[dict[str, Any]] = Field(default_factory=list)


class _LLMSufficiencyPayload(BaseModel):
    score: int = Field(ge=0, le=100)
    gaps: list[str] = Field(default_factory=list)
    checklist_results: list[dict[str, Any]] = Field(default_factory=list)


def _load_checklists() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data" / "checklist_templates.json"
    return path.read_text(encoding="utf-8") and json.loads(path.read_text(encoding="utf-8"))


def _prompt_text() -> str:
    path = Path(__file__).resolve().parents[1] / "prompts" / "sufficiency_evaluator.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return "Evaluate requirement sufficiency and return JSON only."


def _get_by_path(obj: Any, path: str) -> Any:
    parts = path.split(".")
    cur = obj
    for p in parts:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            cur = getattr(cur, p, None)
    return cur


async def evaluate_sufficiency(
    *,
    extracted_entities: ExtractedEntities,
    enriched_context: EnrichedContext,
    intent: str,
    domain: DomainInfo,
    covered_by_agents: list[str] | None = None,
    dynamic_requirements: list[DynamicRequirement] | None = None,
) -> SufficiencyEvaluationResult:
    covered_by_agents = covered_by_agents or []
    dynamic_requirements = dynamic_requirements or []
    checklists = _load_checklists()

    if LLM_MODE != "mock":
        try:
            payload = await LLMClient().call_structured(
                system_prompt=_prompt_text(),
                user_prompt=(
                    f"intent: {intent}\n"
                    f"domain: {domain.domain}/{domain.sub_domain}\n"
                    f"entities: {extracted_entities.model_dump()}\n"
                    f"covered_by_agents: {covered_by_agents}\n"
                    f"dynamic_requirements: {[r.model_dump() for r in dynamic_requirements]}\n"
                    f"matched_agents: {[m.model_dump() for m in enriched_context.agent_matches[:10]]}\n"
                    f"available_tools: {enriched_context.tool_list}\n"
                    f"mcp_errors: {enriched_context.mcp_errors}\n"
                ),
                response_model=_LLMSufficiencyPayload,
            )
            assert isinstance(payload, _LLMSufficiencyPayload)
            return SufficiencyEvaluationResult(
                score=payload.score,
                gaps=payload.gaps,
                checklist_results=payload.checklist_results,
            )
        except Exception:
            pass

    # MVP: поддержка нового контура для intent=new_system и domain/sub_domain
    sub_domain = domain.sub_domain
    items: list[dict[str, Any]] = []
    if intent in checklists:
        intent_block = checklists[intent]
        domain_block = intent_block.get(domain.domain)
        if isinstance(domain_block, dict) and sub_domain in domain_block:
            items = domain_block[sub_domain]

    if not items and dynamic_requirements:
        items = [
            {
                "id": req.id,
                "required_fields": req.required_fields,
                "capabilities": req.capabilities,
            }
            for req in dynamic_requirements
        ]

    if not items:
        # Если чеклист не найден, fallback: оцениваем по наличию capabilities
        if extracted_entities.capabilities:
            return SufficiencyEvaluationResult(score=60, gaps=["no_checklist_template_found"], checklist_results=[])
        return SufficiencyEvaluationResult(score=10, gaps=["no_checklist_template_found", "missing_capabilities"], checklist_results=[])

    entities_dict = extracted_entities.model_dump()
    satisfied = 0
    gaps: list[str] = []
    checklist_results: list[dict[str, Any]] = []

    for item in items:
        required_fields: list[str] = item.get("required_fields", [])
        required_caps: list[str] = item.get("capabilities", [])

        cap_covered = False
        if required_caps:
            cap_covered = any(c in set(covered_by_agents) for c in required_caps)

        field_ok = True
        for f in required_fields:
            val = _get_by_path(entities_dict, f.replace("nfr.", "nfr."))
            if val is None or val == "" or val == []:
                field_ok = False
                break

        passed = cap_covered or field_ok
        checklist_results.append({"id": item.get("id"), "passed": passed, "cap_covered": cap_covered, "required_fields": required_fields})

        if passed:
            satisfied += 1
        else:
            gaps.append(str(item.get("id")))

    score = round((satisfied / max(1, len(items))) * 100)
    score = max(0, min(100, score))

    # Graceful degradation: если MCP недоступны/частично упали, считаем что данных недостаточно
    # и просим клиента предоставить недостающие вводные (edge case из scenarios.md).
    if enriched_context.mcp_errors:
        gaps.append("mcp_unavailable")
        score = min(score, 70)

    return SufficiencyEvaluationResult(score=score, gaps=gaps, checklist_results=checklist_results)

