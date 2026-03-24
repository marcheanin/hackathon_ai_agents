"""
Node 4: Integration Designer
RETRYABLE (вместе с component_architect).
LLM проектирует потоки данных между компонентами.
Работает с готовыми component id — нет риска несоответствия.
"""
import json

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.state import AgentState
from app.llm.client import get_llm_json
from app.schemas.responses import DataFlow


class DataFlowList(BaseModel):
    data_flows: list[DataFlow] = Field(
        ..., description="Список потоков данных между компонентами", min_length=1
    )


SYSTEM_PROMPT = """You are a software architect. Define the data flows between the given components.

For each data flow:
- from_id: source component id (must exist in the components list)
- to_id: target component id (must exist in the components list)
- label: brief description of what data flows (e.g., "HTTP POST /generate", "query vector + top-K results")
- protocol: HTTP, gRPC, AMQP, WebSocket, direct call, or null

Return ONLY a JSON object: {"data_flows": [...]}

Rules:
- Use only component ids from the provided list
- Cover all major interactions
- Avoid redundant flows"""


async def design_integrations_node(state: AgentState) -> dict:
    llm = get_llm_json()

    # Форматируем компоненты для промпта
    components_text = "\n".join(
        f"- {c.id} ({c.type.value}): {c.name} — {c.description}"
        for c in (state.get("components") or [])
    )

    feedback_section = ""
    if state.get("feedback_history"):
        feedback_items = "\n".join(f"- {fb}" for fb in state["feedback_history"])
        feedback_section = f"\n\nPREVIOUS VALIDATION FEEDBACK:\n{feedback_items}"

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"User request: {state['user_request']}\n\n"
                f"Primary pattern: {state.get('primary_pattern', '')}\n\n"
                f"Components:\n{components_text}"
                f"{feedback_section}"
            )
        ),
    ]

    response = await llm.ainvoke(messages)
    result = DataFlowList(**json.loads(response.content))

    # Валидация: фильтруем потоки с несуществующими id
    valid_ids = {c.id for c in (state.get("components") or [])}
    valid_flows = [
        flow
        for flow in result.data_flows
        if flow.from_id in valid_ids and flow.to_id in valid_ids
    ]

    return {"data_flows": valid_flows}
