"""Логгирование промтов и ответов LLM в файл для презентации."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(os.getenv("LLM_LOG_DIR", "/tmp/agent_logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_llm_call(
    agent_name: str,
    node_name: str,
    messages: list,
    response,
    extra: dict | None = None,
) -> None:
    """Записывает промт и ответ LLM в файл /tmp/agent_logs/architect.log"""
    log_file = LOG_DIR / "architect.log"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Извлекаем текст из langchain messages
    prompt_parts = []
    for msg in messages:
        role = getattr(msg, "type", "unknown")
        content = getattr(msg, "content", str(msg))
        prompt_parts.append(f"[{role}] {content}")

    # Извлекаем ответ
    response_content = ""
    if hasattr(response, "content"):
        response_content = response.content or ""
        if not response_content and hasattr(response, "additional_kwargs"):
            response_content = response.additional_kwargs.get("reasoning_content", "")
    else:
        response_content = str(response)

    entry = {
        "timestamp": ts,
        "agent": agent_name,
        "node": node_name,
        "prompt": prompt_parts,
        "response": response_content[:3000],
    }
    if extra:
        entry["extra"] = extra

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"[{ts}] {agent_name} :: {node_name}\n")
        f.write(f"{'='*80}\n\n")
        f.write("--- PROMPT ---\n")
        for part in prompt_parts:
            f.write(f"{part}\n\n")
        f.write("--- RESPONSE ---\n")
        f.write(f"{response_content[:3000]}\n")
        if extra:
            f.write(f"\n--- EXTRA ---\n{json.dumps(extra, ensure_ascii=False, indent=2)}\n")
        f.write("\n")
