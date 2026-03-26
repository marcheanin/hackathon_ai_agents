from __future__ import annotations

import asyncio

from analyst.chains.domain_routing import route_domain
from analyst.chains.entities import extract_entities


def test_domain_detector_client_delivery_support_portal() -> None:
    msg = "Нужен портал тикетов для банков-клиентов с SLA и webhook REST"
    entities_res = asyncio.run(extract_entities(user_message=msg, conversation_history=[], existing_entities=None, domain_hint=None))
    routed = asyncio.run(route_domain(user_message=msg, extracted_entities=entities_res.entities))
    domain = routed.primary
    assert domain.domain == "client_delivery"
    assert domain.sub_domain == "support_portal"
