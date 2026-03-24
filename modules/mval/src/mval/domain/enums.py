from enum import StrEnum


class VerdictType(StrEnum):
    PASS = "PASS"
    CONDITIONAL_PASS = "CONDITIONAL_PASS"
    FAIL = "FAIL"


class ValidationPhase(StrEnum):
    REQUEST = "REQUEST"
    ARCHITECTURE = "ARCHITECTURE"


class SeverityLevel(StrEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PolicyCategory(StrEnum):
    FORMAT = "FORMAT"
    SECURITY = "SECURITY"
    COMPLIANCE = "COMPLIANCE"
    THREAT = "THREAT"


# Ordered severity for comparison
SEVERITY_ORDER: dict[SeverityLevel, int] = {
    SeverityLevel.INFO: 0,
    SeverityLevel.LOW: 1,
    SeverityLevel.MEDIUM: 2,
    SeverityLevel.HIGH: 3,
    SeverityLevel.CRITICAL: 4,
}
