from __future__ import annotations

import asyncio

from analyst.enrichment.code_knowledge import search_snippets
from analyst.models.entities import DomainInfo, ExtractedEntities


def test_code_knowledge_search_engineering_platform_returns_git_template() -> None:
    domain = DomainInfo(domain="engineering_platform", sub_domain="git", confidence=0.8)
    extracted = ExtractedEntities(capabilities=["repository_lifecycle", "merge_request_policy"])
    res = asyncio.run(search_snippets(domain=domain, extracted_entities=extracted, top_k=5))
    assert any(s.id == "tmpl_internal_git_mr_flow" for s in res)

