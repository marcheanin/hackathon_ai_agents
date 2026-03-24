"""
Node 6: Architecture Validator
LLM оценивает черновик архитектуры по 4 критериям.
Триггерит retry или END через conditional edges в graph.py.
"""
import json

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.state import AgentState
from app.config import settings
from app.llm.client import get_llm_json
from app.schemas.responses import ValidationResult


class ValidationOutput(BaseModel):
    completeness: float = Field(..., ge=0.0, le=1.0, description="Все необходимые компоненты присутствуют")
    correctness: float = Field(..., ge=0.0, le=1.0, description="Паттерны применены корректно")
    applicability: float = Field(..., ge=0.0, le=1.0, description="Архитектура решает запрос пользователя")
    feasibility: float = Field(..., ge=0.0, le=1.0, description="Архитектура технически реализуема")
    feedback: str = Field(..., description="Конкретная обратная связь для улучшения архитектуры")
    issues: list[str] = Field(default_factory=list, description="Список конкретных проблем (пустой если одобрено)")


SYSTEM_PROMPT = """You are a senior software architect reviewing an architecture draft for an AI agent system.

Evaluate the architecture on 4 criteria (0.0 to 1.0 each):
1. completeness: Are all necessary components present for the use case?
2. correctness: Are architectural patterns applied correctly?
3. applicability: Does this architecture actually solve the user's request?
4. feasibility: Is this technically feasible to implement?

Return ONLY a JSON object with scores, feedback, and issues list.
Be specific in feedback — mention exact component names or flow issues.
issues list should be empty if approved."""


async def validate_architecture_node(state: AgentState) -> dict:
    llm = get_llm_json()

    components = state.get("components") or []
    data_flows = state.get("data_flows") or []

    components_text = "\n".join(
        f"- {c.id} ({c.type.value}): {c.name} — {c.description}"
        + (f" [tech: {c.technology}]" if c.technology else "")
        for c in components
    )

    flows_text = "\n".join(
        f"- {f.from_id} → {f.to_id}: {f.label}" + (f" [{f.protocol}]" if f.protocol else "")
        for f in data_flows
    )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"User request: {state['user_request']}\n\n"
                f"Primary pattern: {state.get('primary_pattern', '')}\n"
                f"Patterns used: {', '.join(state.get('selected_patterns', []))}\n\n"
                f"Components ({len(components)}):\n{components_text}\n\n"
                f"Data flows ({len(data_flows)}):\n{flows_text}"
            )
        ),
    ]

    response = await llm.ainvoke(messages)
    result = ValidationOutput(**json.loads(response.content))

    scores = {
        "completeness": result.completeness,
        "correctness": result.correctness,
        "applicability": result.applicability,
        "feasibility": result.feasibility,
    }
    score = sum(scores.values()) / len(scores)
    approved = score >= settings.validation_score_threshold

    validation_result = ValidationResult(
        approved=approved,
        score=round(score, 3),
        scores=scores,
        feedback=result.feedback,
        issues=result.issues,
    )

    new_feedback_history = list(state.get("feedback_history", []))
    if not approved and result.feedback:
        new_feedback_history.append(result.feedback)

    return {
        "validation_result": validation_result,
        "is_approved": approved,
        "feedback_history": new_feedback_history,
    }
