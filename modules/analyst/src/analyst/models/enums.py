from enum import StrEnum


class IntentType(StrEnum):
    new_system = "new_system"
    modify_existing = "modify_existing"
    migrate = "migrate"
    integrate = "integrate"
    investigate = "investigate"


class SessionStatus(StrEnum):
    active = "active"
    completed = "completed"
    redirected = "redirected"
    abandoned = "abandoned"


class ConcretizedDecision(StrEnum):
    build_new = "build_new"
    build_with_agent_reuse = "build_with_agent_reuse"
    redirect = "redirect"


class AgentDecisionContribution(StrEnum):
    exact = "exact"
    partial = "partial"
    none = "none"

