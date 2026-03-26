from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PayloadSchemaType

from app.config import settings


def get_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        check_compatibility=False,
    )


async def ensure_collection_exists(client: AsyncQdrantClient) -> None:
    collections = await client.get_collections()
    names = [c.name for c in collections.collections]
    if settings.qdrant_collection not in names:
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


async def check_qdrant_health() -> bool:
    try:
        client = get_qdrant_client()
        await client.get_collections()
        await client.close()
        return True
    except Exception:
        return False
