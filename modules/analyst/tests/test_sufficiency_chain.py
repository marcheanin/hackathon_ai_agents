from __future__ import annotations

import asyncio

from analyst.chains.sufficiency import evaluate_sufficiency
from analyst.models.context import EnrichedContext
from analyst.models.entities import DomainInfo, ExtractedEntities


def test_sufficiency_marks_status_and_supply_chain_as_covered() -> None:
    extracted = ExtractedEntities(
        capabilities=[
            "sms_sending",
            "sms_confirm",
            "vulnerability_scan",
            "sbom_validation",
            "dependency_audit",
        ],
        business_requirements=["Bank support portal ..."],
        system_name="Bank Client Support Portal",
        nfr=None,
        transfer_mode=None,
        limit_or_amount_rules=None,
        sms_confirm=None,
        aml_check_threshold=None,
        auto_cancel_after_minutes=None,
        rollback_strategy=None,
    )
    domain = DomainInfo(domain="client_delivery", sub_domain="support_portal", confidence=0.8)
    enriched = EnrichedContext()

    covered_by_agents = [
        "sms_sending",
        "sms_confirm",
        "vulnerability_scan",
        "sbom_validation",
        "dependency_audit",
    ]

    res = asyncio.run(
        evaluate_sufficiency(
            extracted_entities=extracted,
            enriched_context=enriched,
            intent="new_system",
            domain=domain,
            covered_by_agents=covered_by_agents,
        )
    )

    assert res.score < 100
    assert "status_notification" not in res.gaps
    assert "supply_chain_gate" not in res.gaps
    assert "nfr_rps_latency" in res.gaps
    assert "bank_integration_channel" in res.gaps

