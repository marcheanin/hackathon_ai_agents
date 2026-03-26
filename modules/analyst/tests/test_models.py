from __future__ import annotations

from analyst.models.request import ConcretizedRequest


def test_concretized_request_contracts_example_parses() -> None:
    payload = {
        "concretized_request": {
            "meta": {
                "session_id": "sess_abc123",
                "iterations": 3,
                "confidence_score": 92,
                "unresolved_gaps": [],
                "decision": "build_with_agent_reuse",
            },
            "intent": "new_system",
            "domain": "client_delivery",
            "sub_domain": "support_portal",
            "system_name": "Bank Client Support Portal",
            "business_requirements": [
                "Приём тикетов от банков-клиентов через REST webhook",
                "Лимит 100 000 обращений в месяц на тенанта",
            ],
            "nfr": {
                "rps": 500,
                "peak_rps": 2000,
                "sla_percent": 99.9,
                "latency_p99_ms": 3000,
                "idempotency": "required",
            },
            "integrations": [],
            "constraints": {
                "security": ["SBOM_REQUIRED", "CVE_GATE", "BANK_NDA"],
                "infrastructure": {"cluster": "client-delivery-prod", "database": "PostgreSQL 16", "messaging": "Kafka"},
            },
            "enriched_context": {
                "existing_agents": [
                    {
                        "id": "agent_supply_chain_security",
                        "name": "Supply Chain Security Scanner",
                        "coverage_score": 95,
                        "covered_capabilities": ["vulnerability_scan", "sbom_validation"],
                        "composition_hint": "Обязательный gate перед передачей артефакта банку",
                        "api": "https://internal.vendor.example/agents/supply-chain/v2",
                        "mcp_uri": "mcp://vendor-agents/supply-chain",
                        "protocol": "REST",
                        "auth": "OAuth2",
                    },
                    {
                        "id": "agent_bank_client_ticketing_hub",
                        "name": "Bank Client Ticketing Hub",
                        "coverage_score": 90,
                        "covered_capabilities": ["sms_sending", "client_ticket_ingest", "webhook_ingestion"],
                        "composition_hint": "Единая точка приёма тикетов от банков-тенантов",
                        "api": "https://internal.vendor.example/agents/bank-ticketing/v2",
                        "mcp_uri": "mcp://vendor-agents/bank-ticketing",
                        "protocol": "REST",
                        "auth": "OAuth2",
                    },
                ],
                "agent_overlap_analysis": {
                    "total_capabilities_required": 8,
                    "covered_by_existing_agents": 3,
                    "to_build_from_scratch": 5,
                    "reuse_percentage": 37.5,
                },
                "available_templates": [
                    {"id": "tmpl_bank_ticket_portal", "summary": "Шаблон портала тикетов банка-клиента", "relevance": "high"}
                ],
                "team_standards": {"language": "TypeScript", "framework": "NestJS", "code_style": "vendor-ts-standards-v2"},
                "monitoring": {"required": ["prometheus", "grafana", "elk"], "sla_alerting": True},
            },
        }
    }

    obj = ConcretizedRequest.model_validate(payload)
    assert obj.concretized_request.meta.session_id == "sess_abc123"

