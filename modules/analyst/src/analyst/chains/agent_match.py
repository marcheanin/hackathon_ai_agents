from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from analyst.chains.llm_client import LLMClient
from analyst.config import AGENT_EXACT_MATCH_THRESHOLD, AGENT_PARTIAL_MATCH_THRESHOLD
from analyst.models.agents import AgentEntry, AgentMatch
from analyst.models.enums import AgentDecisionContribution
from analyst.models.entities import ExtractedEntities


class AgentMatchEvaluationResult(BaseModel):
    matches: list[AgentMatch] = Field(default_factory=list)
    best_match: AgentMatch | None = None
    decision: Literal["exact", "partial", "none"] = "none"


class _LLMAgentScore(BaseModel):
    agent_id: str
    score: float = Field(ge=0.0, le=100.0)


class _LLMAgentEvaluationPayload(BaseModel):
    results: list[_LLMAgentScore] = Field(default_factory=list)


def _contribution(score: float) -> AgentDecisionContribution:
    if score >= AGENT_EXACT_MATCH_THRESHOLD:
        return AgentDecisionContribution.exact
    if score >= AGENT_PARTIAL_MATCH_THRESHOLD:
        return AgentDecisionContribution.partial
    return AgentDecisionContribution.none


def _prompt_text() -> str:
    path = Path(__file__).resolve().parents[1] / "prompts" / "agent_match_evaluator.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return "Evaluate relevance score for each candidate agent and return JSON only."


def _keyword_overlap_score(extracted_entities: ExtractedEntities, agent: AgentEntry) -> float:
    required_caps = set(extracted_entities.capabilities or [])
    msg_blob = " ".join(extracted_entities.business_requirements or []).lower()
    agent_tokens = " ".join([agent.name or "", agent.description or "", " ".join(agent.tags or []), " ".join(agent.capabilities or [])]).lower()
    cap_score = 0.0
    if required_caps:
        cap_score = len(required_caps.intersection(set(agent.capabilities or []))) / max(1, len(required_caps))
    if not msg_blob:
        return cap_score * 100.0
    msg_terms = set(t for t in msg_blob.replace(",", " ").replace(".", " ").split() if len(t) >= 4)
    if not msg_terms:
        return cap_score * 100.0
    semantic_hits = sum(1 for t in msg_terms if t in agent_tokens)
    semantic_score = semantic_hits / max(1, len(msg_terms))
    return (0.7 * cap_score + 0.3 * semantic_score) * 100.0


def _llm_user_prompt(extracted_entities: ExtractedEntities, candidates: list[AgentEntry]) -> str:
    short_candidates = [
        {
            "id": a.id,
            "name": a.name,
            "domain": a.domain,
            "sub_domain": a.sub_domain,
            "description": a.description,
            "capabilities": a.capabilities,
            "tags": a.tags,
        }
        for a in candidates
    ]
    return (
        f"user_requirements: {extracted_entities.business_requirements}\n"
        f"requested_capabilities: {extracted_entities.capabilities}\n"
        f"candidate_agents: {short_candidates}"
    )


async def evaluate_agent_match(
    *,
    extracted_entities: ExtractedEntities,
    candidate_agents: list[AgentEntry | dict[str, Any]],
) -> AgentMatchEvaluationResult:
    normalized_candidates: list[AgentEntry] = []
    for c in candidate_agents:
        if isinstance(c, AgentEntry):
            normalized_candidates.append(c)
        else:
            normalized_candidates.append(AgentEntry.model_validate(c))
    if not normalized_candidates:
        return AgentMatchEvaluationResult(matches=[], best_match=None, decision="none")

    required_caps = set(extracted_entities.capabilities or [])
    llm_scores: dict[str, float] = {}
    if normalized_candidates and (required_caps or extracted_entities.business_requirements):
        try:
            payload = await LLMClient().call_structured(
                system_prompt=_prompt_text(),
                user_prompt=_llm_user_prompt(extracted_entities, normalized_candidates),
                response_model=_LLMAgentEvaluationPayload,
            )
            assert isinstance(payload, _LLMAgentEvaluationPayload)
            llm_scores = {row.agent_id: float(row.score) for row in payload.results}
        except Exception:
            llm_scores = {}

    matches: list[AgentMatch] = []
    for agent in normalized_candidates:
        agent_caps = set(agent.capabilities or [])
        covered = sorted(required_caps.intersection(agent_caps))
        uncovered = sorted(required_caps.difference(agent_caps))

        overlap_score = (len(covered) / len(required_caps)) * 100.0 if required_caps else 0.0
        fallback_score = _keyword_overlap_score(extracted_entities, agent)
        llm_score = llm_scores.get(agent.id)
        if llm_score is not None:
            score = (0.6 * llm_score) + (0.4 * overlap_score)
        else:
            score = fallback_score if not required_caps else max(overlap_score, fallback_score)

        matches.append(
            AgentMatch(
                agent_id=agent.id,
                coverage_score=max(0.0, min(100.0, score)),
                covered_capabilities=covered,
                uncovered_capabilities=uncovered,
                decision_contribution=_contribution(score),
            )
        )

    best = max(matches, key=lambda m: m.coverage_score, default=None)
    if best is None:
        return AgentMatchEvaluationResult(matches=[], best_match=None, decision="none")

    if best.coverage_score >= AGENT_EXACT_MATCH_THRESHOLD:
        decision: Literal["exact", "partial", "none"] = "exact"
    elif best.coverage_score >= AGENT_PARTIAL_MATCH_THRESHOLD:
        decision = "partial"
    else:
        decision = "none"

    # Для наглядности возвращаем все matches; в реализации можно ограничить
    return AgentMatchEvaluationResult(matches=matches, best_match=best, decision=decision)

