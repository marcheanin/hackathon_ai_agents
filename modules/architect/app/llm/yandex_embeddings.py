"""Yandex Cloud Foundation Models Embeddings через нативный API."""
from __future__ import annotations

from typing import List

import httpx
from langchain_core.embeddings import Embeddings

from app.config import settings


class YandexEmbeddings(Embeddings):
    """Embedding-модель через Yandex Cloud Foundation Models API."""

    def __init__(
        self,
        api_key: str | None = None,
        folder_id: str | None = None,
        model: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.llm_api_key
        self._folder_id = folder_id or settings.yandex_folder_id
        self._model = model or settings.embedding_model
        self._base_url = "https://llm.api.cloud.yandex.net/foundationModels/v1/textEmbedding"

    @property
    def _model_uri(self) -> str:
        return f"emb://{self._folder_id}/{self._model}"

    def _embed_one(self, text: str) -> list[float]:
        resp = httpx.post(
            self._base_url,
            headers={
                "Authorization": f"Api-Key {self._api_key}",
                "Content-Type": "application/json",
            },
            json={"modelUri": self._model_uri, "text": text},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]

    async def _aembed_one(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self._base_url,
                headers={
                    "Authorization": f"Api-Key {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={"modelUri": self._model_uri, "text": text},
            )
            resp.raise_for_status()
            return resp.json()["embedding"]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_one(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed_one(text)

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        results = []
        for t in texts:
            results.append(await self._aembed_one(t))
        return results

    async def aembed_query(self, text: str) -> List[float]:
        return await self._aembed_one(text)
