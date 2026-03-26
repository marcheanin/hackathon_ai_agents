from __future__ import annotations

from analyst.mcp_servers._data import load_json


async def search_apis(domain: str) -> list[str]:
    catalog = load_json("apis_catalog.json")
    return catalog.get(domain, [])

