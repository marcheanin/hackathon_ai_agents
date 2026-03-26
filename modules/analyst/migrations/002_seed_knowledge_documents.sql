INSERT INTO knowledge_documents (source_type, source_id, title, content, metadata, embedding, embedding_model, embedding_dim)
VALUES
(
  'agent_registry',
  'agent_supply_chain_security',
  'Supply Chain Security Scanner',
  'Сканирование уязвимостей, SBOM, аудит зависимостей для ПО, поставляемого банкам. Domain: security_compliance/supply_chain. Capabilities: vulnerability_scan, sbom_validation, dependency_audit.',
  '{"domain":"security_compliance","sub_domain":"supply_chain","tags":["cve","sbom","security"],"capabilities":["vulnerability_scan","sbom_validation","dependency_audit"]}'::jsonb,
  NULL,
  NULL,
  NULL
),
(
  'agent_registry',
  'agent_bank_client_ticketing_hub',
  'Bank Client Ticketing Hub',
  'Тикеты от банков-клиентов, SLA, эскалации, webhook/REST, уведомления. Domain: client_delivery/support_portal.',
  '{"domain":"client_delivery","sub_domain":"support_portal","tags":["tickets","bank-client"],"capabilities":["client_ticket_ingest","bank_sla_tracking","escalation_workflow","webhook_ingestion","sms_sending","sms_confirm"]}'::jsonb,
  NULL,
  NULL,
  NULL
),
(
  'snippet_summary',
  'tmpl_internal_git_mr_flow',
  'Internal Git + MR governance template',
  'Политики репозитория, branch protection, MR, подписанные релизы. Domain: engineering_platform.',
  '{"domain":"engineering_platform","tags":["git","merge_request_policy","repository_lifecycle"],"stack":["go","kubernetes","postgresql"],"complexity":"medium"}'::jsonb,
  NULL,
  NULL,
  NULL
),
(
  'domain_reference',
  'domain:client_delivery',
  'Domain client_delivery',
  'Domain: client_delivery. Sub-domains: support_portal, releases, contracts.',
  '{"domain":"client_delivery","sub_domains":["support_portal","releases","contracts"]}'::jsonb,
  NULL,
  NULL,
  NULL
),
(
  'domain_reference',
  'domain:engineering_platform',
  'Domain engineering_platform',
  'Domain: engineering_platform. Sub-domains: git, cicd, work_management.',
  '{"domain":"engineering_platform","sub_domains":["git","cicd","work_management"]}'::jsonb,
  NULL,
  NULL,
  NULL
),
(
  'checklist_template',
  'checklist:new_system:client_delivery:support_portal:nfr_rps_latency',
  'Checklist nfr_rps_latency',
  'Intent: new_system. Domain: client_delivery/support_portal. Required fields: nfr.rps, nfr.peak_rps, nfr.latency_p99_ms.',
  '{"intent":"new_system","domain":"client_delivery","sub_domain":"support_portal","required_fields":["nfr.rps","nfr.peak_rps","nfr.latency_p99_ms"],"capabilities":[]}'::jsonb,
  NULL,
  NULL,
  NULL
),
(
  'mcp_api_catalog',
  'apis_catalog.json',
  'apis_catalog.json',
  '{"client_delivery":["Bank Service Desk Connector API","Client SLA & Escalation API"],"engineering_platform":["Internal Git / MR API","CI/CD Orchestrator API"],"security_compliance":["Vulnerability & CVE Aggregator API","SBOM Ingest API"]}',
  '{"source_file":"apis_catalog.json"}'::jsonb,
  NULL,
  NULL,
  NULL
),
(
  'mcp_policies_catalog',
  'policies_catalog.json',
  'policies_catalog.json',
  '{"client_delivery":["NDA & data residency with bank clients"],"engineering_platform":["Branch protection & mandatory review on main"],"security_compliance":["CVE response SLA by severity","SBOM required per release artifact"]}',
  '{"source_file":"policies_catalog.json"}'::jsonb,
  NULL,
  NULL,
  NULL
),
(
  'agent_registry',
  'agent_ai_product_copilot',
  'AI Product Copilot',
  'Внутренний AI-ассистент для продуктового Q&A с RAG и ссылками на источники. Domain: product_knowledge/ai_assistant.',
  '{"domain":"product_knowledge","sub_domain":"ai_assistant","tags":["ai","rag","assistant"],"capabilities":["semantic_doc_qa","rag_answering","embedding_search","source_attribution"]}'::jsonb,
  NULL,
  NULL,
  NULL
),
(
  'agent_registry',
  'agent_incident_command',
  'Incident Command Agent',
  'Оркестрация инцидентов, эскалации on-call, postmortem и RCA. Domain: platform/incident_management.',
  '{"domain":"platform","sub_domain":"incident_management","tags":["incidents","oncall","rca"],"capabilities":["incident_intake","oncall_escalation","postmortem_builder","rca_tracking"]}'::jsonb,
  NULL,
  NULL,
  NULL
),
(
  'agent_registry',
  'agent_oss_license_guard',
  'OSS License Guard',
  'Проверка OSS лицензий и compliance policy gates для зависимостей продукта.',
  '{"domain":"security_compliance","sub_domain":"license_compliance","tags":["oss","license","compliance"],"capabilities":["license_scan","license_policy_gate","third_party_notice_builder"]}'::jsonb,
  NULL,
  NULL,
  NULL
),
(
  'snippet_summary',
  'tmpl_ai_product_qa_assistant',
  'AI product Q&A assistant',
  'RAG-ассистент по внутренней документации с source attribution.',
  '{"domain":"product_knowledge","tags":["rag_answering","semantic_doc_qa","embedding_search"],"stack":["python","fastapi","postgresql"]}'::jsonb,
  NULL,
  NULL,
  NULL
)
ON CONFLICT (source_type, source_id) DO UPDATE
SET
  title = EXCLUDED.title,
  content = EXCLUDED.content,
  metadata = EXCLUDED.metadata,
  updated_at = NOW();
