from __future__ import annotations

from analyst.mcp_servers._data import load_json


async def get_available(domain: str) -> list[str]:
    catalog = load_json("infrastructure_catalog.json")
    return catalog.get(domain, [])

