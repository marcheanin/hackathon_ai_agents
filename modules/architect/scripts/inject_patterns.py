#!/usr/bin/env python3
"""
Загружает архитектурные паттерны из директории scripts/patterns/ в Qdrant.

Использование:
    python scripts/inject_patterns.py
    python scripts/inject_patterns.py --patterns-dir ./custom_patterns --recreate
"""
import argparse
import asyncio
import sys
import uuid
from pathlib import Path

import frontmatter
import httpx
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, PointStruct, VectorParams

# Добавляем корень проекта в sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings


async def _yandex_embed(text: str) -> list[float]:
    """Получает эмбеддинг через нативный Yandex API."""
    # Yandex embedding API имеет лимит на длину текста — обрезаем до ~2000 символов
    text = text[:2000]
    model_uri = f"emb://{settings.yandex_folder_id}/{settings.embedding_model}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://llm.api.cloud.yandex.net/foundationModels/v1/textEmbedding",
            headers={
                "Authorization": f"Api-Key {settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={"modelUri": model_uri, "text": text},
        )
        resp.raise_for_status()
        return resp.json()["embedding"]


async def main(patterns_dir: Path, recreate: bool = False) -> None:
    client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None, check_compatibility=False)

    # Управление коллекцией
    collections = await client.get_collections()
    existing = [c.name for c in collections.collections]

    if settings.qdrant_collection in existing:
        if recreate:
            print(f"Удаляю коллекцию '{settings.qdrant_collection}'...")
            await client.delete_collection(settings.qdrant_collection)
        else:
            print(f"Коллекция '{settings.qdrant_collection}' уже существует. Используйте --recreate для пересоздания.")
            count = await client.count(collection_name=settings.qdrant_collection)
            print(f"Документов в коллекции: {count.count}")
            await client.close()
            return

    print(f"Создаю коллекцию '{settings.qdrant_collection}' (dim={settings.embedding_dimensions})...")
    await client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=VectorParams(
            size=settings.embedding_dimensions,
            distance=Distance.COSINE,
        ),
    )
    await client.create_payload_index(
        collection_name=settings.qdrant_collection,
        field_name="tags",
        field_schema=PayloadSchemaType.KEYWORD,
    )

    # Загрузка документов
    md_files = list(patterns_dir.glob("*.md"))
    if not md_files:
        print(f"Нет .md файлов в {patterns_dir}")
        await client.close()
        return

    print(f"Найдено файлов: {len(md_files)}")

    points: list[PointStruct] = []
    for md_file in md_files:
        post = frontmatter.load(str(md_file))
        content = post.content.strip()
        metadata = dict(post.metadata)

        pattern_name = metadata.get("pattern_name", md_file.stem)
        title = metadata.get("title", pattern_name)
        tags = metadata.get("tags", [])
        use_cases = metadata.get("use_cases", [])
        components = metadata.get("components", [])

        print(f"  Обрабатываю: {title} ({md_file.name})...")

        # Текст для эмбеддинга: заголовок + теги + контент
        embed_text = f"{title}\nTags: {', '.join(tags)}\nUse cases: {', '.join(use_cases)}\n\n{content}"
        vector = await _yandex_embed(embed_text)

        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "pattern_name": pattern_name,
                    "title": title,
                    "content": content,
                    "tags": tags,
                    "use_cases": use_cases,
                    "components": components,
                    "source_file": md_file.name,
                    "version": metadata.get("version", "1.0"),
                },
            )
        )

    # Загрузка батчами по 50
    batch_size = 50
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        await client.upsert(collection_name=settings.qdrant_collection, points=batch)
        print(f"  Загружено {min(i + batch_size, len(points))}/{len(points)} документов")

    count = await client.count(collection_name=settings.qdrant_collection)
    print(f"\n✅ Готово! Документов в коллекции: {count.count}")
    await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inject architecture patterns into Qdrant")
    parser.add_argument(
        "--patterns-dir",
        type=Path,
        default=Path(__file__).parent / "patterns",
        help="Директория с .md файлами паттернов",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Пересоздать коллекцию (удалить существующую)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.patterns_dir, args.recreate))
