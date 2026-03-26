from __future__ import annotations

import json

import structlog
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from mval.domain.enums import SeverityLevel
from mval.domain.models import PolicyRule, ThreatFinding
from mval.redteam.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

logger = structlog.get_logger("mval.redteam")


class RedTeamAgent:
    """AI Red Teaming agent using Yandex Cloud LLM via LangChain."""

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._llm = init_chat_model(
            model,
            model_provider="openai",
            base_url=base_url,
            api_key=api_key,
            temperature=0.2,
        )

    async def analyze(
        self, artifact: dict, threat_matrix: list[PolicyRule]
    ) -> list[ThreatFinding]:
        threat_descriptions = "\n".join(
            f"- {t.name}: {t.rule_expression}" for t in threat_matrix
        )
        user_prompt = USER_PROMPT_TEMPLATE.format(
            artifact_json=json.dumps(artifact, indent=2, ensure_ascii=False),
            threat_descriptions=threat_descriptions or "(no specific threats)",
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        try:
            response = await self._llm.ainvoke(messages)
            findings_raw = json.loads(response.content)
        except json.JSONDecodeError:
            logger.warning("redteam_invalid_json", response=str(response.content)[:500])
            return []
        except Exception as exc:
            logger.error("redteam_llm_error", error=str(exc))
            raise

        findings: list[ThreatFinding] = []
        for item in findings_raw:
            try:
                severity = SeverityLevel(item.get("severity", "MEDIUM").upper())
            except ValueError:
                severity = SeverityLevel.MEDIUM
            findings.append(
                ThreatFinding(
                    threat_name=item.get("threat_name", "unknown"),
                    description=item.get("description", ""),
                    severity=severity,
                    attack_vector=item.get("attack_vector", ""),
                    mitigation=item.get("mitigation", ""),
                    confidence=float(item.get("confidence", 0.5)),
                )
            )
        return findings
