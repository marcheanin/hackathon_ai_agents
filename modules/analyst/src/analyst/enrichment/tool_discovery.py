from __future__ import annotations

from typing import Any

from analyst.models.entities import DomainInfo, ExtractedEntities


async def discover_tools(domain: DomainInfo, extracted_entities: ExtractedEntities) -> list[str]:
    """Discovery tools.

    В фазе 4 для MVP возвращаем статический список (позже заменим на чтение Tool Registry / MCP Registry).
    """

    return [
        "arch_template_search",
        "security_policy_lookup",
        "agent_catalog_search",
        "code_snippet_search",
    ]

