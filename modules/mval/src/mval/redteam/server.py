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
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", "llama3.2"),
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
