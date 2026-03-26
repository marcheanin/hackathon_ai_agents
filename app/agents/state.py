from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages

from app.schemas.responses import Component, DataFlow, ValidationResult


class AgentState(TypedDict):
    # Input
    user_request: str
    context: dict | None

    # RAG (заполняется один раз — в retrieve_patterns)
    retrieved_patterns: list[dict]

    # Pattern selection (заполняется один раз — в select_patterns)
    selected_patterns: list[str]
    primary_pattern: str
    pattern_reasoning: str

    # Component design (retryable — в design_components)
    components: list[Component] | None

    # Integration design (retryable — в design_integrations)
    data_flows: list[DataFlow] | None

    # Diagram synthesis (детерминированный — в synthesize_diagram)
    mermaid_diagram: str | None
    yaml_spec: str | None

    # Validation
    validation_result: ValidationResult | None
    feedback_history: list[str]

    # LangGraph message history (для отладки)
    messages: Annotated[list, add_messages]

    # Control
    iteration_count: int
    is_approved: bool
    error: str | None
