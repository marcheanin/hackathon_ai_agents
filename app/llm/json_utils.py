"""Утилиты для робастного парсинга JSON из LLM-ответов."""
import json
import re


def parse_llm_json(content: str) -> dict:
    """Парсит JSON из ответа LLM, обрабатывая типичные проблемы:
    - Markdown code fences (```json ... ```)
    - Лишний текст до/после JSON
    - Пустой content
    """
    if not content or not content.strip():
        raise ValueError("LLM returned empty content")

    text = content.strip()

    # Убираем markdown code fences
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()

    # Пробуем напрямую
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Ищем первый JSON-объект в тексте
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Failed to parse JSON from LLM response: {text[:200]}...")
