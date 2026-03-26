from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from analyst.chains.llm_client import LLMClient
from analyst.config import LLM_MODE
from analyst.models.context import DynamicRequirement, EnrichedContext
from analyst.models.entities import DomainInfo, ExtractedEntities


class _DynamicRequirementPayload(BaseModel):
    requirements: list[DynamicRequirement] = Field(default_factory=list)


def _requirements_prompt() -> str:
    path = Path(__file__).resolve().parents[1] / "prompts" / "sufficiency_evaluator.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return "Generate dynamic requirements list as JSON only."


def _base_dynamic_for_domain(domain: DomainInfo) -> list[DynamicRequirement]:
    if domain.domain == "client_delivery" and domain.sub_domain == "support_portal":
        return [
            DynamicRequirement(
                id="dyn_sla_matrix",
                description="Определена SLA-матрица по severity/tier банка-клиента.",
                required_fields=["business_requirements"],
                source="domain_rule",
                priority="high",
            ),
            DynamicRequirement(
                id="dyn_escalation_contacts",
                description="Определены контактные группы эскалации и график on-call.",
                required_fields=["business_requirements"],
                source="domain_rule",
                priority="medium",
            ),
        ]
    return []


def _capability_driven_requirements(extracted: ExtractedEntities) -> list[DynamicRequirement]:
    caps = set(extracted.capabilities or [])
    out: list[DynamicRequirement] = []

    if {"vulnerability_scan", "sbom_validation", "dependency_audit"} & caps:
        out.append(
            DynamicRequirement(
                id="dyn_cve_sbom_gate",
                description="Укажите gate для security-сканирования: порог CVSS, блокирующие/неблокирующие CVE, обязательность SBOM.",
                required_fields=["aml_check_threshold"],
                capabilities=["vulnerability_scan", "sbom_validation", "dependency_audit"],
                source="capability_rule",
                priority="high",
                activation_condition="has_security_supply_chain_caps",
            )
        )

    if {"repository_lifecycle", "merge_request_policy", "branch_protection"} & caps:
        out.append(
            DynamicRequirement(
                id="dyn_git_governance",
                description="Укажите branch policy: required reviewers, signed commits/tags, правила merge.",
                required_fields=["business_requirements"],
                capabilities=["repository_lifecycle", "merge_request_policy"],
                source="capability_rule",
                priority="high",
                activation_condition="has_git_caps",
            )
        )

    if {"pipeline_template_library", "build_artifact_signing", "deployment_gate"} & caps:
        out.append(
            DynamicRequirement(
                id="dyn_release_promotion_flow",
                description="Опишите promotion flow (dev->staging->prod) и критерии прохождения deployment gate.",
                required_fields=["rollback_strategy"],
                capabilities=["deployment_gate", "build_artifact_signing"],
                source="capability_rule",
                priority="high",
                activation_condition="has_cicd_caps",
            )
        )

    return out


def _fallback_build_dynamic_requirements(
    *,
    extracted_entities: ExtractedEntities,
    domain: DomainInfo,
    enriched_context: EnrichedContext,
) -> list[DynamicRequirement]:
    reqs = _base_dynamic_for_domain(domain) + _capability_driven_requirements(extracted_entities)

    # Add policy-driven requirements when available from MCP
    policies = enriched_context.mcp_data.get("policies", []) if enriched_context.mcp_data else []
    if policies:
        reqs.append(
            DynamicRequirement(
                id="dyn_policy_alignment",
                description="Подтвердите соответствие ключевым политикам из каталога (security/compliance/release).",
                required_fields=["business_requirements"],
                source="mcp_policy",
                priority="medium",
            )
        )

    # De-duplicate by id while keeping first occurrence
    uniq: dict[str, DynamicRequirement] = {}
    for r in reqs:
        if r.id not in uniq:
            uniq[r.id] = r
    return list(uniq.values())


async def build_dynamic_requirements(
    *,
    extracted_entities: ExtractedEntities,
    domain: DomainInfo,
    enriched_context: EnrichedContext,
) -> list[DynamicRequirement]:
    if LLM_MODE == "mock":
        return _fallback_build_dynamic_requirements(
            extracted_entities=extracted_entities,
            domain=domain,
            enriched_context=enriched_context,
        )
    try:
        payload = await LLMClient().call_structured(
            system_prompt=_requirements_prompt(),
            user_prompt=(
                f"intent: {extracted_entities.intent}\n"
                f"domain: {domain.domain}/{domain.sub_domain}\n"
                f"capabilities: {extracted_entities.capabilities}\n"
                f"matched_agents: {[m.model_dump() for m in enriched_context.agent_matches[:8]]}\n"
                f"agent_candidates: {[a.model_dump() for a in enriched_context.agent_candidates[:8]]}\n"
                f"available_tools: {enriched_context.tool_list}\n"
                f"policies: {enriched_context.mcp_data.get('policies', []) if enriched_context.mcp_data else []}\n"
            ),
            response_model=_DynamicRequirementPayload,
        )
        assert isinstance(payload, _DynamicRequirementPayload)
        if payload.requirements:
            return payload.requirements
    except Exception:
        pass
    return _fallback_build_dynamic_requirements(
        extracted_entities=extracted_entities,
        domain=domain,
        enriched_context=enriched_context,
    )
