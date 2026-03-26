from __future__ import annotations

from analyst.mcp_servers._data import load_json


async def get_team_info(domain: str) -> dict:
    teams = load_json("teams_registry.json")
    return teams.get(domain, {})

