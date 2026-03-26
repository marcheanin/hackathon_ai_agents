from __future__ import annotations

from typing import Any, Type
import json

import httpx
from pydantic import BaseModel

from analyst.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_MODE, LLM_TIMEOUT_S


class LLMClient:
    """LLM client.

    В MVP по умолчанию используется детерминированный mock-режим (цепочки считают результат сами).
    Live-режим оставлен для будущей интеграции с DeepSeek/OpenAI-совместимым API.
    """

    def __init__(self, mode: str | None = None) -> None:
        self.mode = mode or LLM_MODE

    async def call_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[BaseModel],
        model: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> BaseModel:
        if self.mode == "mock":
            raise RuntimeError("LLMClient.call_structured should not be used in mock mode; chains implement deterministic logic.")

        if not LLM_API_KEY:
            raise RuntimeError("LLM_API_KEY is not set; cannot call live LLM.")

        # Yandex Cloud LLM API base URL приходит как .../v1
        url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": model or LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }

        # Пытаемся запросить JSON-объект. Поддержка зависит от конкретного провайдера.
        payload["response_format"] = {"type": "json_object"}
        if extra:
            payload.update(extra)

        async with httpx.AsyncClient(timeout=LLM_TIMEOUT_S) as client:
            resp = await client.post(url, headers={"Authorization": f"Api-Key {LLM_API_KEY}"}, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        json_payload = json.loads(content)
        return response_model.model_validate(json_payload)

