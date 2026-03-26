"""
Node 1: RAG Retriever
Выполняется ОДИН РАЗ в начале пайплайна.
Семантический поиск релевантных архитектурных паттернов в Qdrant.
"""
from qdrant_client.models import models

from app.agents.state import AgentState
from app.config import settings
from app.llm.client import get_embeddings
from app.rag.client import get_qdrant_client


async def retrieve_patterns_node(state: AgentState) -> dict:
    embeddings = get_embeddings()
    client = get_qdrant_client()

    query_vector = await embeddings.aembed_query(state["user_request"])

    results = await client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        limit=settings.qdrant_top_k,
        with_payload=True,
    )
    await client.close()

    patterns = [
        {
            "pattern_name": point.payload["pattern_name"],
            "title": point.payload.get("title", point.payload["pattern_name"]),
            "content": point.payload["content"],
            "score": point.score,
            "tags": point.payload.get("tags", []),
            "use_cases": point.payload.get("use_cases", []),
        }
        for point in results.points
    ]

    from app.llm.logger import log_llm_call
    from langchain_core.messages import HumanMessage as _HM
    log_llm_call(
        "architect", "rag_retriever",
        [_HM(content=f"RAG query: {state['user_request']}")],
        type("R", (), {"content": "\n".join(f"- {p['pattern_name']} (score={p['score']:.3f})" for p in patterns)})(),
    )

    return {"retrieved_patterns": patterns}
