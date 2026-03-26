"""Pydantic models и TypedDict контракты для Analyst module."""

from analyst.models.agents import AgentEntry, AgentMatch, AgentOverlapAnalysis, ExistingAgentRef
from analyst.models.context import EnrichedContext
from analyst.models.entities import (
    Constraints,
    DomainInfo,
    ExtractedEntities,
    Integration,
    InfrastructureConstraints,
    NFR,
)
from analyst.models.enums import (
    AgentDecisionContribution,
    ConcretizedDecision,
    IntentType,
    SessionStatus,
)
from analyst.models.redirect import RedirectResponse
from analyst.models.request import ConcretizedMeta, ConcretizedNFR, ConcretizedRequest, ConcretizedRequestPayload
from analyst.models.session import Conversation, ConversationTurn, SessionState
from analyst.models.snippets import SnippetSummary

__all__ = [
    "AgentEntry",
    "AgentMatch",
    "AgentOverlapAnalysis",
    "ExistingAgentRef",
    "EnrichedContext",
    "Constraints",
    "DomainInfo",
    "ExtractedEntities",
    "Integration",
    "InfrastructureConstraints",
    "NFR",
    "AgentDecisionContribution",
    "ConcretizedDecision",
    "IntentType",
    "SessionStatus",
    "RedirectResponse",
    "ConcretizedMeta",
    "ConcretizedNFR",
    "ConcretizedRequest",
    "ConcretizedRequestPayload",
    "Conversation",
    "ConversationTurn",
    "SessionState",
    "SnippetSummary",
]

