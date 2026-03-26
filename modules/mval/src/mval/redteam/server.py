"""Standalone FastAPI server for the Red Teaming sidecar container."""
from __future__ import annotations

import os

from fastapi import FastAPI
from pydantic import BaseModel

from mval.domain.models import PolicyRule, ThreatFinding
from mval.redteam.agent import RedTeamAgent

app = FastAPI(title="МВАЛ Red Teaming Sidecar")

_agent: RedTeamAgent | None = None


def _get_agent() -> RedTeamAgent:
    global _agent
    if _agent is None:
        _agent = RedTeamAgent(
            base_url=os.getenv("YANDEX_BASE_URL", "https://llm.api.cloud.yandex.net/v1"),
            api_key=os.getenv("YANDEX_API_KEY", ""),
            model=os.getenv("LLM_MODEL_NAME", "deepseek-v32/latest"),
        )
    return _agent


class AnalyzeRequest(BaseModel):
    artifact: dict
    threat_matrix: list[PolicyRule]


class AnalyzeResponse(BaseModel):
    findings: list[ThreatFinding]
    error: str | None = None


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(body: AnalyzeRequest):
    try:
        agent = _get_agent()
        findings = await agent.analyze(body.artifact, body.threat_matrix)
        return AnalyzeResponse(findings=findings)
    except Exception as exc:
        return AnalyzeResponse(findings=[], error=str(exc))


@app.get("/health")
async def health():
    return {"status": "ok"}
