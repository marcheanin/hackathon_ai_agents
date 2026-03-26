"""
Node 5: Diagram Synthesizer
ДЕТЕРМИНИРОВАННЫЙ — без LLM, 100% корректный синтаксис Mermaid.
Генерирует Mermaid C4Component диаграмму и YAML-спек из структурированных данных.
"""
import yaml

from app.agents.state import AgentState
from app.schemas.responses import Component, DataFlow


def _component_to_mermaid(c: Component) -> str:
    tech = f", \"{c.technology}\"" if c.technology else ""
    desc = c.description.replace('"', "'")[:80]
    return f'        Component({c.id}, "{c.name}"{tech}, "{desc}")'


def _flow_to_mermaid(flow: DataFlow) -> str:
    label = flow.label.replace('"', "'")
    if flow.protocol:
        return f'    Rel({flow.from_id}, {flow.to_id}, "{label}", "{flow.protocol}")'
    return f'    Rel({flow.from_id}, {flow.to_id}, "{label}")'


def _build_mermaid(
    title: str,
    components: list[Component],
    data_flows: list[DataFlow],
    primary_pattern: str,
) -> str:
    component_lines = "\n".join(_component_to_mermaid(c) for c in components)
    flow_lines = "\n".join(_flow_to_mermaid(f) for f in data_flows)

    return f"""C4Component
    title {title} [{primary_pattern}]

    Container_Boundary(system, "AI Agent System") {{
{component_lines}
    }}

{flow_lines}"""


def _build_yaml_spec(
    title: str,
    description: str,
    primary_pattern: str,
    patterns_used: list[str],
    components: list[Component],
    data_flows: list[DataFlow],
) -> str:
    spec = {
        "title": title,
        "description": description,
        "architecture": {
            "primary_pattern": primary_pattern,
            "patterns_used": patterns_used,
        },
        "components": [
            {
                "id": c.id,
                "name": c.name,
                "type": c.type.value,
                "description": c.description,
                "technology": c.technology,
                "dependencies": c.dependencies,
            }
            for c in components
        ],
        "data_flows": [
            {
                "from": f.from_id,
                "to": f.to_id,
                "label": f.label,
                "protocol": f.protocol,
            }
            for f in data_flows
        ],
    }
    return yaml.dump(spec, allow_unicode=True, default_flow_style=False, sort_keys=False)


async def synthesize_diagram_node(state: AgentState) -> dict:
    components = state.get("components") or []
    data_flows = state.get("data_flows") or []
    primary_pattern = state.get("primary_pattern", "layered-architecture")
    patterns_used = state.get("selected_patterns", [primary_pattern])

    # Генерируем заголовок из запроса пользователя (первые 60 символов)
    request_short = state["user_request"][:60].rstrip()
    title = f"Architecture: {request_short}{'...' if len(state['user_request']) > 60 else ''}"
    description = state["user_request"]

    mermaid_diagram = _build_mermaid(title, components, data_flows, primary_pattern)
    yaml_spec = _build_yaml_spec(title, description, primary_pattern, patterns_used, components, data_flows)

    return {
        "mermaid_diagram": mermaid_diagram,
        "yaml_spec": yaml_spec,
    }
