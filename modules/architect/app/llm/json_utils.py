"""Утилиты для робастного парсинга JSON из LLM-ответов."""
import json
import re


def _find_balanced_json(text: str) -> str | None:
    """Находит первый сбалансированный JSON-объект в тексте."""
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        ch = text[i]

        if escape:
            escape = False
            continue

        if ch == "\\":
            if in_string:
                escape = True
            continue

        if ch == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    return None


def parse_llm_json(content) -> dict:
    """Парсит JSON из ответа LLM, обрабатывая типичные проблемы:
    - Markdown code fences (```json ... ```)
    - Лишний текст до/после JSON
    - Пустой content
    - Обрезанный JSON (незакрытые скобки)
    - DeepSeek: content может быть пустым, а ответ — в reasoning_content (additional_kwargs)
    """
    # Поддержка AIMessage объектов (langchain)
    if hasattr(content, "content"):
        msg = content
        text_content = msg.content or ""
        # DeepSeek через Yandex Cloud кладёт ответ в reasoning_content
        if not text_content and hasattr(msg, "additional_kwargs"):
            text_content = msg.additional_kwargs.get("reasoning_content", "")
        content = text_content

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

    # Ищем первый сбалансированный JSON-объект
    balanced = _find_balanced_json(text)
    if balanced:
        try:
            return json.loads(balanced)
        except json.JSONDecodeError:
            pass

    # Fallback: жадный regex
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Failed to parse JSON from LLM response: {text[:200]}...")
