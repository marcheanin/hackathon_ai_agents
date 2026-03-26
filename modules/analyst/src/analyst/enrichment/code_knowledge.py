from __future__ import annotations

import json
from pathlib import Path

from analyst.models.entities import DomainInfo, ExtractedEntities
from analyst.models.snippets import SnippetSummary


def _load_snippets() -> list[dict]:
    path = Path(__file__).resolve().parents[1] / "data" / "snippets_summaries.json"
    return json.loads(path.read_text(encoding="utf-8"))


async def search_snippets(domain: DomainInfo, extracted_entities: ExtractedEntities, top_k: int = 5) -> list[SnippetSummary]:
    snippets = _load_snippets()
    required_domain = domain.domain
    caps = set(extracted_entities.capabilities or [])

    scored: list[tuple[int, SnippetSummary]] = []
    for s in snippets:
        snippet = SnippetSummary.model_validate(s)
        if snippet.domain and snippet.domain != required_domain:
            continue
        # Score by tag overlap with capabilities as a proxy
        tag_overlap = len(caps.intersection(set(snippet.tags or [])))
        scored.append((tag_overlap, snippet))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:top_k]]

