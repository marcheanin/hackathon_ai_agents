from __future__ import annotations

import asyncio

from analyst.chains.intent import classify_intent
from analyst.models.enums import IntentType


def test_intent_classifier_portal_is_new_system() -> None:
    res = asyncio.run(
        classify_intent(
            user_message="Нужен портал тикетов для банков-клиентов с SLA и уведомлениями по SMS",
            conversation_history=[],
        )
    )
    assert res.intent == IntentType.new_system

