#!/usr/bin/env python3
"""Seed Analyst knowledge_documents with synthetic data.

Usage:
    python modules/analyst/scripts/seed_knowledge_documents.py \
      --db-url postgresql://postgres:password@localhost:5432/interview
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import asyncpg


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _analyst_data_dir() -> Path:
    # .../modules/analyst/scripts -> .../modules/analyst/src/analyst/data
    return Path(__file__).resolve().parents[1] / "src" / "analyst" / "data"


def _make_documents() -> list[dict[str, Any]]:
    data_dir = _analyst_data_dir()
    docs: list[dict[str, Any]] = []

    # Agent registry -> one doc per agent
    agents = _read_json(data_dir / "agents.json")
    for agent in agents:
        source_id = str(agent.get("id"))
        title = str(agent.get("name") or source_id)
        api = agent.get("api", {}) if isinstance(agent.get("api"), dict) else {}
        sla = agent.get("sla", {}) if isinstance(agent.get("sla"), dict) else {}
        deps = agent.get("dependencies", []) or []
        hints = agent.get("composition_hints", []) or []
        tags = agent.get("tags", []) or []
        capabilities = agent.get("capabilities", []) or []
        content = (
            f"Description:\n{agent.get('description', '')}\n\n"
            f"Domain:\n{agent.get('domain')}/{agent.get('sub_domain')}\n\n"
            f"Identity:\n"
            f"- id: {agent.get('id')}\n"
            f"- version: {agent.get('version')}\n"
            f"- status: {agent.get('status')}\n"
            f"- owner_team: {agent.get('owner_team')}\n"
            f"- contact: {agent.get('contact')}\n\n"
            f"Purpose & Usage Notes:\n"
            f"- composable: {agent.get('composable')}\n"
            f"- tags: {', '.join(map(str, tags))}\n"
            f"- composition_hints: {', '.join(map(str, hints))}\n\n"
            f"Capabilities:\n{', '.join(map(str, capabilities))}\n\n"
            f"Dependencies:\n{', '.join(map(str, deps)) if deps else '(none)'}\n\n"
            f"API:\n"
            f"- protocol: {api.get('protocol')}\n"
            f"- base_url: {api.get('base_url')}\n"
            f"- auth: {api.get('auth')}\n"
            f"- rate_limit: {api.get('rate_limit')}\n"
            f"- docs_url: {api.get('docs_url')}\n\n"
            f"SLA:\n{json.dumps(sla, ensure_ascii=False)}"
        )
        metadata = {
            "domain": agent.get("domain"),
            "sub_domain": agent.get("sub_domain"),
            "tags": agent.get("tags", []),
            "capabilities": agent.get("capabilities", []),
            "owner_team": agent.get("owner_team"),
            "status": agent.get("status"),
            "source_file": "agents.json",
        }
        docs.append(
            {
                "source_type": "agent_registry",
                "source_id": source_id,
                "title": title,
                "content": content,
                "metadata": metadata,
            }
        )

    # Snippet summaries -> one doc per snippet
    snippets = _read_json(data_dir / "snippets_summaries.json")
    for sn in snippets:
        source_id = str(sn.get("id"))
        title = str(sn.get("name") or source_id)
        tags = sn.get("tags", []) or []
        stack = sn.get("stack", []) or []
        complexity = sn.get("complexity")
        files_count = sn.get("files_count")
        content = (
            f"Summary:\n{sn.get('summary', '')}\n\n"
            f"Domain: {sn.get('domain', '')}\n"
            f"Tags: {', '.join(map(str, tags))}\n"
            f"Stack: {', '.join(map(str, stack))}\n\n"
            f"Complexity: {complexity}\n"
            f"Files count: {files_count}\n"
        )
        metadata = {
            "domain": sn.get("domain"),
            "tags": sn.get("tags", []),
            "stack": sn.get("stack", []),
            "complexity": sn.get("complexity"),
            "files_count": sn.get("files_count"),
            "source_file": "snippets_summaries.json",
        }
        docs.append(
            {
                "source_type": "snippet_summary",
                "source_id": source_id,
                "title": title,
                "content": content,
                "metadata": metadata,
            }
        )

    # Domains reference
    domains = _read_json(data_dir / "domains.json")
    for row in domains.get("domains", []):
        domain = row.get("domain")
        source_id = f"domain:{domain}"
        title = f"Domain {domain}"
        content = f"Domain: {domain}\nSub-domains: {', '.join(row.get('sub_domains', []))}"
        metadata = {"domain": domain, "sub_domains": row.get("sub_domains", []), "source_file": "domains.json"}
        docs.append(
            {
                "source_type": "domain_reference",
                "source_id": source_id,
                "title": title,
                "content": content,
                "metadata": metadata,
            }
        )

    # Checklist templates (flattened)
    checklists = _read_json(data_dir / "checklist_templates.json")
    for intent_key, intent_block in checklists.items():
        for domain_key, sub_block in intent_block.items():
            if not isinstance(sub_block, dict):
                continue
            for sub_domain_key, items in sub_block.items():
                if not isinstance(items, list):
                    continue
                for item in items:
                    item_id = item.get("id", "unknown")
                    source_id = f"checklist:{intent_key}:{domain_key}:{sub_domain_key}:{item_id}"
                    title = f"Checklist {item_id}"
                    required_fields = item.get("required_fields", []) or []
                    caps = item.get("capabilities", []) or []
                    content = (
                        f"Intent: {intent_key}\n"
                        f"Domain: {domain_key}/{sub_domain_key}\n"
                        f"Description:\n{item.get('description', '')}\n\n"
                        f"Required fields: {', '.join(map(str, required_fields)) if required_fields else '(none)'}\n"
                        f"Required capabilities: {', '.join(map(str, caps)) if caps else '(none)'}\n"
                    )
                    metadata = {
                        "intent": intent_key,
                        "domain": domain_key,
                        "sub_domain": sub_domain_key,
                        "required_fields": item.get("required_fields", []),
                        "capabilities": item.get("capabilities", []),
                        "source_file": "checklist_templates.json",
                    }
                    docs.append(
                        {
                            "source_type": "checklist_template",
                            "source_id": source_id,
                            "title": title,
                            "content": content,
                            "metadata": metadata,
                        }
                    )

    # MCP catalogs as whole documents
    mcp_files = [
        ("mcp_api_catalog", "apis_catalog.json"),
        ("mcp_policies_catalog", "policies_catalog.json"),
        ("mcp_infrastructure_catalog", "infrastructure_catalog.json"),
        ("mcp_teams_registry", "teams_registry.json"),
        ("mcp_monitoring_standards", "monitoring_standards.json"),
    ]
    for source_type, filename in mcp_files:
        obj = _read_json(data_dir / filename)
        docs.append(
            {
                "source_type": source_type,
                "source_id": filename,
                "title": filename,
                "content": json.dumps(obj, ensure_ascii=False),
                "metadata": {"source_file": filename},
            }
        )

    return docs


async def seed(db_url: str) -> None:
    docs = _make_documents()
    conn = await asyncpg.connect(db_url)
    try:
        for d in docs:
            await conn.execute(
                """
                INSERT INTO knowledge_documents
                    (source_type, source_id, title, content, metadata, embedding, embedding_model, embedding_dim, created_at, updated_at)
                VALUES
                    ($1, $2, $3, $4, $5::jsonb, NULL, NULL, NULL, NOW(), NOW())
                ON CONFLICT (source_type, source_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    content = EXCLUDED.content,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                """,
                d["source_type"],
                d["source_id"],
                d["title"],
                d["content"],
                json.dumps(d["metadata"], ensure_ascii=False),
            )
        print(f"Seeded {len(docs)} knowledge documents.")
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed analyst knowledge_documents from synthetic JSON data")
    parser.add_argument(
        "--db-url",
        default="postgresql://postgres:password@localhost:5432/interview",
        help="PostgreSQL connection URL",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.db_url))


if __name__ == "__main__":
    main()

