from __future__ import annotations

from typing import Any

from analyst.mcp_servers._data import load_json


def _agent_matches(
    agent: dict[str, Any],
    *,
    domain: str | None,
    capabilities: list[str] | None,
    tags: list[str] | None,
    status: str | None,
) -> bool:
    if domain is not None and agent.get("domain") != domain:
        return False
    if status is not None and agent.get("status") != status:
        return False

    if capabilities:
        # Консервативно: считаем совпадением, если есть пересечение capabilities
        caps = set(agent.get("capabilities", []))
        if caps.isdisjoint(set(capabilities)):
            return False

    if tags:
        agent_tags = set(agent.get("tags", []))
        if agent_tags.isdisjoint(set(tags)):
            return False

    return True


async def search_agents(
    domain: str | None = None,
    capabilities: list[str] | None = None,
    tags: list[str] | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    agents = load_json("agents.json")
    return [a for a in agents if _agent_matches(a, domain=domain, capabilities=capabilities, tags=tags, status=status)]


async def get_agent(agent_id: str) -> dict[str, Any]:
    agents = load_json("agents.json")
    for a in agents:
        if a.get("id") == agent_id:
            return a
    raise KeyError(f"Agent not found: {agent_id}")


async def get_agent_api_spec(agent_id: str) -> dict[str, Any]:
    agent = await get_agent(agent_id)
    return agent.get("api", {})


async def check_agent_health(agent_id: str | None = None) -> dict[str, Any]:
    if agent_id is None:
        # Заглушка: возвращаем средние агрегаты
        agents = load_json("agents.json")
        count = len(agents)
        avg_avail = sum(a.get("sla", {}).get("availability_percent", 0.0) for a in agents) / max(1, count)
        avg_latency = sum(a.get("sla", {}).get("latency_p99_ms", 0) for a in agents) / max(1, count)
        return {"avg_availability_percent": avg_avail, "avg_latency_p99_ms": avg_latency}

    agent = await get_agent(agent_id)
    sla = agent.get("sla", {})
    return {
        "agent_id": agent_id,
        "availability_percent": sla.get("availability_percent"),
        "latency_p99_ms": sla.get("latency_p99_ms"),
        "status": "ok",
    }

