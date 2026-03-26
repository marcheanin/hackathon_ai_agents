from langgraph.graph import END, START, StateGraph

from app.agents.nodes.arch_validator import validate_architecture_node
from app.agents.nodes.component_architect import design_components_node
from app.agents.nodes.diagram_synthesizer import synthesize_diagram_node
from app.agents.nodes.integration_designer import design_integrations_node
from app.agents.nodes.pattern_selector import select_patterns_node
from app.agents.nodes.rag_retriever import retrieve_patterns_node
from app.agents.state import AgentState
from app.config import settings


def _should_retry(state: AgentState) -> str:
    """
    Conditional edge после validate_architecture.
    Pure function — без LLM, только читает state.
    """
    if state.get("is_approved"):
        return "approved"
    if state.get("iteration_count", 0) >= settings.max_retries:
        return "max_retries"
    return "retry"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Регистрация узлов
    graph.add_node("retrieve_patterns", retrieve_patterns_node)
    graph.add_node("select_patterns", select_patterns_node)
    graph.add_node("design_components", design_components_node)
    graph.add_node("design_integrations", design_integrations_node)
    graph.add_node("synthesize_diagram", synthesize_diagram_node)
    graph.add_node("validate_architecture", validate_architecture_node)

    # Рёбра: линейный пайплайн
    graph.add_edge(START, "retrieve_patterns")
    graph.add_edge("retrieve_patterns", "select_patterns")
    graph.add_edge("select_patterns", "design_components")
    graph.add_edge("design_components", "design_integrations")
    graph.add_edge("design_integrations", "synthesize_diagram")
    graph.add_edge("synthesize_diagram", "validate_architecture")

    # Условный retry loop: validate → approved/retry/max_retries
    graph.add_conditional_edges(
        "validate_architecture",
        _should_retry,
        {
            "approved": END,
            "retry": "design_components",   # retry только с design_components (пропуская RAG + pattern_selection)
            "max_retries": END,
        },
    )

    return graph.compile()


# Единственный экземпляр скомпилированного графа
compiled_graph = build_graph()
