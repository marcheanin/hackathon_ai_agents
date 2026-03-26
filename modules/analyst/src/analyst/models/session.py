from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from analyst.models.context import EnrichedContext
from analyst.models.entities import DomainInfo, ExtractedEntities
from analyst.models.enums import SessionStatus
from analyst.models.agents import AgentMatch
from analyst.models.snippets import SnippetSummary


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant", "system"] | str
    text: str
    timestamp: datetime = Field(default_factory=_utcnow)


class Conversation(BaseModel):
    turns: list[ConversationTurn] = Field(default_factory=list)


class SessionState(BaseModel):
    session_id: str
    status: SessionStatus = SessionStatus.active
    iteration: int = 0

    conversation: Conversation = Field(default_factory=Conversation)

    # Pipeline artifacts
    extracted_entities: ExtractedEntities = Field(default_factory=ExtractedEntities)
    domain: DomainInfo | None = None
    enriched_context: EnrichedContext = Field(default_factory=EnrichedContext)
    agent_matches: list[AgentMatch] = Field(default_factory=list)
    snippet_matches: list[SnippetSummary] = Field(default_factory=list)

    # Evaluation
    sufficiency_score: int | None = None
    gaps: list[str] = Field(default_factory=list)
    already_asked: list[str] = Field(default_factory=list)

    # Decision
    decision: str | None = None

