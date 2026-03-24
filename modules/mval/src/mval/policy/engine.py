from __future__ import annotations

import re

import structlog

from mval.domain.enums import (
    SEVERITY_ORDER,
    PolicyCategory,
    SeverityLevel,
    ValidationPhase,
)
from mval.domain.models import ComplianceCheckResult, ComplianceReport, PolicyRule
from mval.policy.cache import PolicyCache
from mval.policy.circuit_breaker import CircuitBreaker
from mval.policy.repository import PolicyRepository

logger = structlog.get_logger("mval.policy_engine")


def _resolve_jsonpath(artifact: dict, path: str) -> object | None:
    """Minimal JSONPath resolver: supports $.field and $.field.sub only."""
    if not path.startswith("$."):
        return None
    keys = path[2:].split(".")
    current: object = artifact
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


def _evaluate_rule(rule: PolicyRule, artifact: dict) -> ComplianceCheckResult:
    """Evaluate a single policy rule against an artifact.

    Rule expression mini-language (prototype):
        exists:$.field            — field must exist and be non-empty
        type:$.field=array        — field must be of given type
        min_len:$.field=N         — array/string length >= N
        max_len:$.field=N         — array/string length <= N
        max_val:$.field=N         — numeric value <= N
        regex_not:$.field=PATTERN — field must NOT match regex
        allowed:$.field=a,b,c     — field value must be in allowed list
    """
    expr = rule.rule_expression
    try:
        if expr.startswith("exists:"):
            path = expr[len("exists:"):]
            value = _resolve_jsonpath(artifact, path)
            passed = value is not None and value != "" and value != []
            detail = f"{path} {'present' if passed else 'missing or empty'}"

        elif expr.startswith("type:"):
            rest = expr[len("type:"):]
            path, expected_type = rest.split("=", 1)
            value = _resolve_jsonpath(artifact, path)
            type_map = {"array": list, "object": dict, "string": str, "number": (int, float)}
            passed = isinstance(value, type_map.get(expected_type, object))
            detail = f"{path} type {'matches' if passed else 'does not match'} {expected_type}"

        elif expr.startswith("min_len:"):
            rest = expr[len("min_len:"):]
            path, min_val = rest.split("=", 1)
            value = _resolve_jsonpath(artifact, path)
            passed = value is not None and len(value) >= int(min_val)
            detail = f"{path} length {'>='+min_val if passed else 'below '+min_val}"

        elif expr.startswith("max_len:"):
            rest = expr[len("max_len:"):]
            path, max_val = rest.split("=", 1)
            value = _resolve_jsonpath(artifact, path)
            passed = value is not None and len(value) <= int(max_val)
            detail = f"{path} length {'<='+max_val if passed else 'exceeds '+max_val}"

        elif expr.startswith("max_val:"):
            rest = expr[len("max_val:"):]
            path, max_val = rest.split("=", 1)
            value = _resolve_jsonpath(artifact, path)
            if value is None:
                passed = True  # optional field
                detail = f"{path} not present (optional)"
            else:
                passed = float(value) <= float(max_val)
                detail = f"{path} value {'<='+max_val if passed else 'exceeds '+max_val}"

        elif expr.startswith("regex_not:"):
            rest = expr[len("regex_not:"):]
            path, pattern = rest.split("=", 1)
            value = _resolve_jsonpath(artifact, path)
            if value is None or not isinstance(value, str):
                passed = True
                detail = f"{path} not a string or absent"
            else:
                passed = re.search(pattern, value, re.IGNORECASE) is None
                detail = f"{path} {'clean' if passed else 'matches forbidden pattern'}"

        elif expr.startswith("allowed:"):
            rest = expr[len("allowed:"):]
            path, allowed_csv = rest.split("=", 1)
            value = _resolve_jsonpath(artifact, path)
            allowed = [v.strip() for v in allowed_csv.split(",")]
            passed = value in allowed
            detail = f"{path} value '{value}' {'in' if passed else 'not in'} allowed set"

        elif expr.startswith("each_has:"):
            # each_has:$.components.config=field_name
            rest = expr[len("each_has:"):]
            path, field = rest.split("=", 1)
            items = _resolve_jsonpath(artifact, path)
            if not isinstance(items, list):
                passed = False
                detail = f"{path} is not an array"
            else:
                missing = [
                    i for i, item in enumerate(items)
                    if not isinstance(item, dict) or field not in item
                ]
                passed = len(missing) == 0
                detail = (
                    f"all items have '{field}'"
                    if passed
                    else f"items at indices {missing} missing '{field}'"
                )

        elif expr.startswith("none_match:"):
            # none_match:$.components.config=REGEX
            rest = expr[len("none_match:"):]
            path, pattern = rest.split("=", 1)
            items = _resolve_jsonpath(artifact, path)
            if not isinstance(items, list):
                passed = True
                detail = f"{path} is not an array (skip)"
            else:
                matches = []
                for i, item in enumerate(items):
                    text = str(item)
                    if re.search(pattern, text, re.IGNORECASE):
                        matches.append(i)
                passed = len(matches) == 0
                detail = (
                    "no forbidden patterns found"
                    if passed
                    else f"forbidden pattern found at indices {matches}"
                )

        else:
            passed = False
            detail = f"unknown rule expression: {expr}"

    except Exception as exc:
        passed = False
        detail = f"rule evaluation error: {exc}"

    return ComplianceCheckResult(
        rule_id=rule.id,
        rule_name=rule.name,
        passed=passed,
        severity=rule.severity,
        detail=detail,
    )


class PolicyEngine:
    """Loads policy rules from cache/БДвал and evaluates artifacts."""

    def __init__(
        self,
        repository: PolicyRepository,
        cache: PolicyCache,
        circuit_breaker: CircuitBreaker,
    ) -> None:
        self._repo = repository
        self._cache = cache
        self._cb = circuit_breaker

    async def _load_rules(self, phase: ValidationPhase) -> list[PolicyRule]:
        """Load rules: cache → БДвал (with circuit breaker)."""
        # Try cache first
        cached = await self._cache.get_rules(phase)
        if cached is not None:
            return cached

        # Cache miss — try БДвал
        if not self._cb.allow_request():
            raise RuntimeError("no_policies_available: БДвал circuit breaker OPEN")

        try:
            rules = await self._repo.get_rules(phase)
            self._cb.record_success()
            await self._cache.set_rules(phase, rules)
            return rules
        except Exception as exc:
            self._cb.record_failure()
            logger.warning("bdval_fetch_failed", error=str(exc))
            raise RuntimeError(f"no_policies_available: {exc}") from exc

    async def evaluate(
        self, phase: ValidationPhase, artifact: dict
    ) -> ComplianceReport:
        rules = await self._load_rules(phase)
        # Filter out THREAT category — those are for Red Teaming only
        check_rules = [r for r in rules if r.category != PolicyCategory.THREAT]
        results = [_evaluate_rule(rule, artifact) for rule in check_rules]

        failed = [r for r in results if not r.passed]
        highest: SeverityLevel | None = None
        if failed:
            highest = max(failed, key=lambda r: SEVERITY_ORDER[r.severity]).severity

        return ComplianceReport(
            phase=phase,
            results=results,
            passed_count=len(results) - len(failed),
            failed_count=len(failed),
            highest_severity=highest,
        )

    async def get_threat_matrix(self) -> list[PolicyRule]:
        rules = await self._load_rules(ValidationPhase.ARCHITECTURE)
        return [r for r in rules if r.category == PolicyCategory.THREAT]
