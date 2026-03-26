#!/usr/bin/env python3
"""Apply DB migration and seed synthetic knowledge data.

Usage:
    python scripts/bootstrap_knowledge_db.py \
      --db-url postgresql://postgres:password@analyst-postgres:5432/interview
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import asyncpg

from seed_knowledge_documents import seed


async def apply_migration(db_url: str, migration_path: Path) -> None:
    conn = await asyncpg.connect(db_url)
    try:
        sql = migration_path.read_text(encoding="utf-8")
        await conn.execute(sql)
    finally:
        await conn.close()


async def bootstrap(db_url: str, migration_path: Path) -> None:
    print(f"[bootstrap] applying migration: {migration_path}")
    await apply_migration(db_url, migration_path)
    print("[bootstrap] migration applied")

    print("[bootstrap] seeding knowledge_documents")
    await seed(db_url)
    print("[bootstrap] seeding completed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap analyst knowledge DB (migrate + seed)")
    parser.add_argument(
        "--db-url",
        default="postgresql://postgres:password@analyst-postgres:5432/interview",
        help="PostgreSQL connection URL",
    )
    parser.add_argument(
        "--migration-path",
        default=str(Path(__file__).resolve().parents[1] / "migrations" / "001_create_knowledge_documents.sql"),
        help="Path to migration SQL file",
    )
    args = parser.parse_args()
    asyncio.run(bootstrap(args.db_url, Path(args.migration_path)))


if __name__ == "__main__":
    main()

