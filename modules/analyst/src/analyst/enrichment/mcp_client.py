from __future__ import annotations

import asyncio
from typing import Any

from analyst.models.entities import DomainInfo, ExtractedEntities
from analyst.observability import pipeline_log
from analyst.mcp_servers.bank_api_catalog import search_apis
from analyst.mcp_servers.infra_catalog import get_available
from analyst.mcp_servers.observability import get_monitoring_standards
from analyst.mcp_servers.security_policy import get_policies
from analyst.mcp_servers.team_registry import get_team_info


async def fetch_mcp_data(
    domain: DomainInfo,
    entities: ExtractedEntities,
    *,
    session_id: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Параллельно запрашиваем синтетические MCP-источники.

    При ошибках — возвращаем частичные данные и ошибки отдельно (graceful degradation).
    """

    sid = session_id or "?"
    pipeline_log(sid, "enrichment→mcp", "fetch_start", domain=domain.domain, sub_domain=domain.sub_domain)

    errors: list[str] = []
    mcp_data: dict[str, Any] = {}

    async def _safe(name: str, coro):
        try:
            return name, await coro
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {type(e).__name__}: {e}")
            return name, None

    tasks = [
        _safe("apis", search_apis(domain.domain)),
        _safe("policies", get_policies(domain.domain)),
        _safe("infrastructure", get_available(domain.domain)),
        _safe("team", get_team_info(domain.domain)),
        _safe("monitoring", get_monitoring_standards()),
    ]

    results = await asyncio.gather(*tasks)
    for name, value in results:
        if value is not None:
            mcp_data[name] = value

    pipeline_log(
        sid,
        "enrichment→mcp",
        "fetch_done",
        keys_ok=list(mcp_data.keys()),
        errors_count=len(errors),
        errors_preview=errors[:5] if errors else None,
    )

    return mcp_data, errors

