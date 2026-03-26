"""Утилита для форматирования context из state в текст для LLM."""
import json


def _extract_concretized_summary(input_data: dict) -> str:
    """Извлекает ключевую информацию из concretized_request в компактном виде."""
    cr = input_data
    # Navigate nested structure
    if "concretized_request" in cr:
        cr = cr["concretized_request"]
    if "concretized_request" in cr:
        cr = cr["concretized_request"]

    lines = []

    # Meta
    meta = cr.get("meta", {})
    if meta.get("decision"):
        lines.append(f"Decision strategy: {meta['decision']}")

    # Domain
    if cr.get("domain"):
        lines.append(f"Domain: {cr['domain']}/{cr.get('sub_domain', '')}")
    if cr.get("system_name"):
        lines.append(f"System name: {cr['system_name']}")

    # NFR
    nfr = cr.get("nfr", {})
    if nfr:
        nfr_parts = []
        if nfr.get("rps"):
            nfr_parts.append(f"RPS={nfr['rps']}")
        if nfr.get("peak_rps"):
            nfr_parts.append(f"peak={nfr['peak_rps']}")
        if nfr.get("latency_p99_ms"):
            nfr_parts.append(f"p99={nfr['latency_p99_ms']}ms")
        if nfr_parts:
            lines.append(f"NFR: {', '.join(nfr_parts)}")

    # Enriched context
    ec = cr.get("enriched_context", {})

    # Existing agents
    for agent in ec.get("existing_agents", []):
        caps = ", ".join(agent.get("covered_capabilities", []))
        hint = agent.get("composition_hint", "")
        api = agent.get("api", "")
        mcp = agent.get("mcp_uri", "")
        lines.append(
            f"REUSE AGENT: {agent['name']} (id={agent['id']}, coverage={agent.get('coverage_score', 0)}%)\n"
            f"  Capabilities: {caps}\n"
            f"  Hint: {hint}\n"
            f"  API: {api}, MCP: {mcp}, Auth: {agent.get('auth', '')}"
        )

    # Overlap analysis
    overlap = ec.get("agent_overlap_analysis", {})
    if overlap:
        lines.append(
            f"Agent overlap: {overlap.get('covered_by_existing_agents', 0)}/{overlap.get('total_capabilities_required', 0)} "
            f"capabilities covered, {overlap.get('to_build_from_scratch', 0)} to build, "
            f"reuse={overlap.get('reuse_percentage', 0)}%"
        )

    # Team standards
    ts = ec.get("team_standards", {})
    if ts:
        lines.append(f"Team standards: {ts.get('language', '')}/{ts.get('framework', '')} ({ts.get('code_style', '')})")

    # MCP data
    mcp_data = ec.get("mcp_data", {})
    if mcp_data.get("infrastructure"):
        lines.append(f"Infrastructure: {', '.join(mcp_data['infrastructure'])}")
    if mcp_data.get("policies"):
        lines.append(f"Policies: {'; '.join(mcp_data['policies'])}")
    if mcp_data.get("apis"):
        lines.append(f"Available APIs: {', '.join(mcp_data['apis'])}")

    # Monitoring
    mon = ec.get("monitoring", {})
    if mon.get("required"):
        lines.append(f"Monitoring: {', '.join(mon['required'])} (SLA alerting: {mon.get('sla_alerting', False)})")

    # Templates
    for tmpl in ec.get("available_templates", []):
        lines.append(f"Template: {tmpl.get('id', '')} — {tmpl.get('summary', '')}")

    return "\n".join(lines)


def format_context(state: dict) -> str:
    """Форматирует state['context'] в текстовую секцию для HumanMessage."""
    context = state.get("context")
    if not context:
        return ""

    parts = []

    # Системные инструкции (краткое описание роли)
    if context.get("system_instructions"):
        parts.append(f"=== ARCHITECT ROLE ===\n{context['system_instructions']}")

    # Структурированная выжимка из input_data
    if context.get("input_data"):
        summary = _extract_concretized_summary(context["input_data"])
        if summary:
            parts.append(f"=== ANALYST MODULE OUTPUT (key data) ===\n{summary}")

    # Fallback
    if not parts:
        ctx_str = json.dumps(context, ensure_ascii=False, indent=2) if isinstance(context, dict) else str(context)
        parts.append(f"=== ADDITIONAL CONTEXT ===\n{ctx_str}")

    return "\n\n" + "\n\n".join(parts)
