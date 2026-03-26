from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from analyst.chains.llm_client import LLMClient
from analyst.config import LLM_MODE
from analyst.models.enums import IntentType


class IntentClassifierResult(BaseModel):
    intent: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


def _heuristic_classify(user_message: str) -> IntentClassifierResult:
    text = user_message.lower()
    if "миграц" in text or "migrate" in text:
        return IntentClassifierResult(intent=IntentType.migrate, confidence=0.8, reasoning="Ключевые слова миграции.")
    # «интеграция» часто в формулировках канала к банку / API — не путать с intent integrate.
    _new_build_markers = (
        "портал",
        "тикет",
        "нужен сервис",
        "нужна систем",
        "нужен агент",
        "нужен портал",
        "sbom",
        "cve",
        "реестр продукт",
        "пайплайн",
        " ci",
        "cicd",
        "git",
        "merge request",
    )
    if ("интеграц" in text or "integrate" in text) and not any(m in text for m in _new_build_markers):
        return IntentClassifierResult(intent=IntentType.integrate, confidence=0.78, reasoning="Ключевые слова интеграции.")
    if "измен" in text or "доработ" in text or "modify" in text:
        return IntentClassifierResult(intent=IntentType.modify_existing, confidence=0.75, reasoning="Ключевые слова изменения.")
    if "исслед" in text or "разобрать" in text or "investigate" in text:
        return IntentClassifierResult(intent=IntentType.investigate, confidence=0.7, reasoning="Ключевые слова исследования.")
    return IntentClassifierResult(
        intent=IntentType.new_system,
        confidence=0.86,
        reasoning="Нет признаков интеграции/миграции — считаем запросом на новую систему.",
    )


def _intent_system_prompt() -> str:
    path = Path(__file__).resolve().parent.parent / "prompts" / "intent_classifier.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return (
            "Classify user intent as one of: new_system, modify_existing, migrate, integrate, investigate. "
            "Reply with JSON only: {\"intent\":\"...\",\"confidence\":0.0-1.0,\"reasoning\":\"...\"}"
        )


def _format_user_prompt(user_message: str, conversation_history: list[dict[str, Any]] | None) -> str:
    parts = [f"Сообщение пользователя:\n{user_message.strip()}"]
    if conversation_history:
        lines: list[str] = []
        for msg in conversation_history[-12:]:
            role = str(msg.get("role", "user"))
            content = str(msg.get("content", "")).strip()
            if not content:
                continue
            if len(content) > 1500:
                content = content[:1500] + "…"
            lines.append(f"{role}: {content}")
        if lines:
            parts.append("Недавний контекст:\n" + "\n".join(lines))
    return "\n\n".join(parts)


async def classify_intent(
    *,
    user_message: str,
    conversation_history: list[dict[str, Any]] | None = None,
    llm_client: Any | None = None,
) -> IntentClassifierResult:
    if LLM_MODE == "mock":
        return _heuristic_classify(user_message)

    client: LLMClient = llm_client if llm_client is not None else LLMClient()
    user_prompt = _format_user_prompt(user_message, conversation_history)
    try:
        out = await client.call_structured(
            system_prompt=_intent_system_prompt(),
            user_prompt=user_prompt,
            response_model=IntentClassifierResult,
        )
        assert isinstance(out, IntentClassifierResult)
        return out
    except Exception:
        return _heuristic_classify(user_message)

