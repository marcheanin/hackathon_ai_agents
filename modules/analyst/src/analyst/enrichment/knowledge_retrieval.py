from __future__ import annotations

from typing import Any

from analyst.config import DATABASE_URL
from analyst.models.context import KnowledgeHit
from analyst.models.entities import DomainInfo, ExtractedEntities


async def retrieve_knowledge_hits(
    *,
    domain: DomainInfo,
    entities: ExtractedEntities,
    limit: int = 8,
) -> list[KnowledgeHit]:
    if not DATABASE_URL:
        return []
    try:
        import asyncpg  # type: ignore
    except Exception:
        return []

    query_text = " ".join((entities.business_requirements or []) + (entities.capabilities or []))
    if not query_text.strip():
        query_text = f"{domain.domain} {domain.sub_domain or ''}".strip()
    sql = """
        SELECT
            source_type,
            title,
            LEFT(content, 500) AS excerpt,
            metadata
        FROM knowledge_documents
        WHERE to_tsvector('simple', content::text) @@ plainto_tsquery('simple', $1)
        ORDER BY created_at DESC
        LIMIT $2
    """
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows: list[Any] = await conn.fetch(sql, query_text, limit)
    finally:
        await conn.close()
    out: list[KnowledgeHit] = []
    for row in rows:
        out.append(
            KnowledgeHit(
                source_type=str(row["source_type"]),
                title=str(row["title"]),
                excerpt=str(row["excerpt"]),
                metadata=dict(row["metadata"] or {}),
            )
        )
    return out
