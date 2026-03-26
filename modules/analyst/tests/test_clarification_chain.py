from __future__ import annotations

import asyncio

from analyst.chains.clarification import generate_clarification


def test_clarification_generator_questions_from_gaps() -> None:
    res = asyncio.run(generate_clarification(gaps=["nfr_rps_latency", "bank_integration_channel"], conversation_history=[], already_asked=[]))
    assert len(res.questions) >= 1
    joined = " ".join(res.questions).lower()
    assert "rps" in joined
    assert "банк" in joined or "webhook" in joined or "rest" in joined

