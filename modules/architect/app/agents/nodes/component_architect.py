"""
Node 3: Component Architect
RETRYABLE — при отклонении валидатором возвращается сюда с feedback.
LLM проектирует список компонентов системы на основе запроса и паттернов.
"""
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.context_utils import format_context
from app.agents.state import AgentState
from app.llm.client import get_llm_json
from app.llm.json_utils import parse_llm_json
from app.schemas.responses import Component, ComponentType


class ComponentList(BaseModel):
    components: list[Component] = Field(
        ..., description="Список всех компонентов архитектуры", min_length=2
    )


SYSTEM_PROMPT = """You are a software architect. Design the list of components for an AI agent system.

For each component provide:
- id: unique snake_case identifier
- name: human-readable name
- type: one of [llm_agent, tool, memory, orchestrator, api_gateway, database, queue, external]
- description: what this component does (1-2 sentences)
- technology: specific technology (e.g., FastAPI, Qdrant, LangGraph) or null
- dependencies: list of component ids this depends on (can be empty list)

Return ONLY a JSON object: {"components": [...]}

Design focused, minimal components that directly address the user request."""


async def design_components_node(state: AgentState) -> dict:
    llm = get_llm_json()

    # Получаем контент выбранных паттернов
    selected_names = set(state.get("selected_patterns", []))
    selected_contents = [
        f"Pattern: {p['title']}\n{p['content'][:800]}"
        for p in state["retrieved_patterns"]
        if p["pattern_name"] in selected_names
    ]
    patterns_text = "\n\n---\n\n".join(selected_contents) if selected_contents else "No specific patterns selected"

    # Feedback секция для retry
    feedback_section = ""
    if state.get("feedback_history"):
        feedback_items = "\n".join(f"- {fb}" for fb in state["feedback_history"])
        feedback_section = f"\n\nPREVIOUS VALIDATION FEEDBACK (address these issues):\n{feedback_items}"

    context_section = format_context(state)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"User request: {state['user_request']}{context_section}\n\n"
                f"Primary pattern: {state.get('primary_pattern', 'layered-architecture')}\n"
                f"Patterns reasoning: {state.get('pattern_reasoning', '')}\n\n"
                f"Reference patterns:\n{patterns_text}"
                f"{feedback_section}"
            )
        ),
    ]

    response = await llm.ainvoke(messages)
    result = ComponentList(**parse_llm_json(response))

    return {
        "components": result.components,
        "iteration_count": state.get("iteration_count", 0) + 1,
    }
