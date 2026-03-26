"""
Юнит-тесты узлов LangGraph с mock LLM и Qdrant.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.nodes.diagram_synthesizer import synthesize_diagram_node
from app.agents.state import AgentState
from app.schemas.responses import Component, ComponentType, DataFlow


def _base_state(**overrides) -> AgentState:
    state: AgentState = {
        "user_request": "Нужен агент для мониторинга цен",
        "context": None,
        "retrieved_patterns": [],
        "selected_patterns": ["rag-agent", "multi-agent-orchestration"],
        "primary_pattern": "rag-agent",
        "pattern_reasoning": "Best fit for retrieval-based system",
        "components": None,
        "data_flows": None,
        "mermaid_diagram": None,
        "yaml_spec": None,
        "validation_result": None,
        "feedback_history": [],
        "messages": [],
        "iteration_count": 0,
        "is_approved": False,
        "error": None,
    }
    state.update(overrides)
    return state


@pytest.mark.asyncio
async def test_synthesize_diagram_generates_mermaid():
    components = [
        Component(
            id="api_handler",
            name="API Handler",
            type=ComponentType.API_GATEWAY,
            description="Receives HTTP requests",
            technology="FastAPI",
            dependencies=[],
        ),
        Component(
            id="llm_agent",
            name="LLM Agent",
            type=ComponentType.LLM_AGENT,
            description="Processes requests with LLM",
            technology="LangChain",
            dependencies=["api_handler"],
        ),
    ]
    data_flows = [
        DataFlow(from_id="api_handler", to_id="llm_agent", label="User request", protocol="HTTP"),
    ]
    state = _base_state(components=components, data_flows=data_flows)

    result = await synthesize_diagram_node(state)

    assert "mermaid_diagram" in result
    assert "yaml_spec" in result
    assert "C4Component" in result["mermaid_diagram"]
    assert "api_handler" in result["mermaid_diagram"]
    assert "llm_agent" in result["mermaid_diagram"]
    assert "components:" in result["yaml_spec"]


@pytest.mark.asyncio
async def test_synthesize_diagram_filters_empty_flows():
    components = [
        Component(id="a", name="A", type=ComponentType.LLM_AGENT, description="Agent A", dependencies=[]),
    ]
    state = _base_state(components=components, data_flows=[])

    result = await synthesize_diagram_node(state)
    assert result["mermaid_diagram"] is not None
    assert result["yaml_spec"] is not None


@pytest.mark.asyncio
async def test_synthesize_diagram_yaml_structure():
    components = [
        Component(id="db", name="Database", type=ComponentType.DATABASE, description="Stores data", technology="Qdrant", dependencies=[]),
    ]
    state = _base_state(components=components, data_flows=[])

    result = await synthesize_diagram_node(state)

    import yaml
    parsed = yaml.safe_load(result["yaml_spec"])
    assert "title" in parsed
    assert "components" in parsed
    assert parsed["components"][0]["id"] == "db"
    assert parsed["components"][0]["type"] == "database"
