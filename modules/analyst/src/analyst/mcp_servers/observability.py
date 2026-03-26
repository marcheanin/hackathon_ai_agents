from __future__ import annotations

from analyst.mcp_servers._data import load_json


async def get_monitoring_standards() -> dict:
    return load_json("monitoring_standards.json")

