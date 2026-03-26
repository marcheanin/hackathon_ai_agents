#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MARKER = "\n\n[auto-expanded-details]\n"


def _as_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if x is not None]
    if isinstance(v, str):
        return [v]
    return [str(v)]


def _schema_required(schema: Any) -> list[str]:
    if not isinstance(schema, dict):
        return []
    req = schema.get("required")
    return _as_list(req)


def _schema_fields(schema: Any) -> list[str]:
    if not isinstance(schema, dict):
        return []
    fields = schema.get("fields")
    return _as_list(fields)


def _api_block(api: Any) -> list[str]:
    if not isinstance(api, dict):
        return []
    return [
        f"protocol: {api.get('protocol')}",
        f"base_url: {api.get('base_url')}",
        f"auth: {api.get('auth')}",
        f"rate_limit: {api.get('rate_limit')}",
        f"docs_url: {api.get('docs_url')}",
    ]


def _json_dumps_short(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return str(obj)


def _expand_agent(agent: dict[str, Any]) -> dict[str, Any]:
    desc = str(agent.get("description") or "")
    if MARKER in desc:
        return agent

    capabilities = _as_list(agent.get("capabilities"))
    tags = _as_list(agent.get("tags"))
    deps = _as_list(agent.get("dependencies"))
    hints = _as_list(agent.get("composition_hints"))
    input_schema = agent.get("input_schema")
    output_schema = agent.get("output_schema")

    api = agent.get("api") or {}
    sla = agent.get("sla") or {}

    input_req = _schema_required(input_schema)
    output_fields = _schema_fields(output_schema)

    details = []
    details.append(f"agent_id: {agent.get('id')}")
    details.append(f"domain: {agent.get('domain')}/{agent.get('sub_domain')}")
    if tags:
        details.append(f"tags: {', '.join(tags)}")
    if capabilities:
        details.append(f"capabilities: {', '.join(capabilities)}")
    if input_req:
        details.append(f"input.required: {', '.join(input_req)}")
    if output_fields:
        details.append(f"output.fields: {', '.join(output_fields)}")
    if deps:
        details.append(f"dependencies: {', '.join(deps)}")
    if hints:
        details.append(f"composition_hints: {', '.join(hints)}")

    details.append("api:")
    details.extend([f"- {line}" for line in _api_block(api)])
    details.append("sla:")
    details.append(_json_dumps_short(sla))

    agent["description"] = desc + MARKER + "\n".join(details).strip() + "\n"
    return agent


def _expand_snippet(sn: dict[str, Any]) -> dict[str, Any]:
    summary = str(sn.get("summary") or "")
    if MARKER in summary:
        return sn

    tags = _as_list(sn.get("tags"))
    domain = sn.get("domain")
    stack = _as_list(sn.get("stack"))
    complexity = sn.get("complexity")
    files_count = sn.get("files_count")

    details = [
        f"snippet_id: {sn.get('id')}",
        f"domain: {domain}",
    ]
    if tags:
        details.append(f"tags: {', '.join(tags)}")
    if stack:
        details.append(f"stack: {', '.join(stack)}")
    if complexity is not None:
        details.append(f"complexity: {complexity}")
    if files_count is not None:
        details.append(f"files_count: {files_count}")

    sn["summary"] = summary + MARKER + "\n" + "\n".join(details).strip() + "\n"
    return sn


def _data_dir() -> Path:
    # .../modules/analyst/scripts -> .../modules/analyst/src/analyst/data
    return Path(__file__).resolve().parents[1] / "src" / "analyst" / "data"


def main() -> None:
    data_dir = _data_dir()
    agents_path = data_dir / "agents.json"
    snippets_path = data_dir / "snippets_summaries.json"

    agents = json.loads(agents_path.read_text(encoding="utf-8"))
    snippets = json.loads(snippets_path.read_text(encoding="utf-8"))

    if not isinstance(agents, list):
        raise RuntimeError("agents.json must be a JSON list")
    if not isinstance(snippets, list):
        raise RuntimeError("snippets_summaries.json must be a JSON list")

    agents2 = [_expand_agent(a) for a in agents]
    snippets2 = [_expand_snippet(s) for s in snippets]

    agents_path.write_text(json.dumps(agents2, ensure_ascii=False, indent=2), encoding="utf-8")
    snippets_path.write_text(json.dumps(snippets2, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Expanded: agents={len(agents2)} snippets={len(snippets2)}")


if __name__ == "__main__":
    main()

