"""Tests for PolicyEngine — rule evaluation and cache/repo loading."""
from __future__ import annotations

from uuid import uuid4

import pytest

from mval.domain.enums import (
    PolicyCategory,
    SeverityLevel,
    ValidationPhase,
)
from mval.domain.models import PolicyRule
from mval.policy.circuit_breaker import CircuitBreaker, CircuitState
from mval.policy.engine import PolicyEngine, _evaluate_rule, _resolve_jsonpath


# ── JSONPath resolver ───────────────────────────────────────────────


class TestResolveJsonpath:
    def test_simple_field(self):
        assert _resolve_jsonpath({"name": "Alice"}, "$.name") == "Alice"

    def test_nested_field(self):
        assert _resolve_jsonpath({"a": {"b": 42}}, "$.a.b") == 42

    def test_missing_field(self):
        assert _resolve_jsonpath({"a": 1}, "$.b") is None

    def test_invalid_prefix(self):
        assert _resolve_jsonpath({"a": 1}, "a") is None


# ── Rule expression evaluation ──────────────────────────────────────


def _rule(expression: str, severity: SeverityLevel = SeverityLevel.MEDIUM) -> PolicyRule:
    return PolicyRule(
        id=uuid4(),
        name="test_rule",
        phase=ValidationPhase.REQUEST,
        category=PolicyCategory.FORMAT,
        severity=severity,
        rule_expression=expression,
        description="test",
    )


class TestExists:
    def test_exists_present(self):
        r = _evaluate_rule(_rule("exists:$.name"), {"name": "Alice"})
        assert r.passed is True

    def test_exists_missing(self):
        r = _evaluate_rule(_rule("exists:$.name"), {})
        assert r.passed is False

    def test_exists_empty_string(self):
        r = _evaluate_rule(_rule("exists:$.name"), {"name": ""})
        assert r.passed is False

    def test_exists_empty_list(self):
        r = _evaluate_rule(_rule("exists:$.items"), {"items": []})
        assert r.passed is False


class TestType:
    def test_type_array(self):
        r = _evaluate_rule(_rule("type:$.items=array"), {"items": [1, 2]})
        assert r.passed is True

    def test_type_array_fail(self):
        r = _evaluate_rule(_rule("type:$.items=array"), {"items": "not_array"})
        assert r.passed is False

    def test_type_string(self):
        r = _evaluate_rule(_rule("type:$.name=string"), {"name": "hi"})
        assert r.passed is True

    def test_type_object(self):
        r = _evaluate_rule(_rule("type:$.cfg=object"), {"cfg": {"a": 1}})
        assert r.passed is True


class TestMinLen:
    def test_min_len_pass(self):
        r = _evaluate_rule(_rule("min_len:$.name=3"), {"name": "Alice"})
        assert r.passed is True

    def test_min_len_fail(self):
        r = _evaluate_rule(_rule("min_len:$.name=10"), {"name": "Hi"})
        assert r.passed is False

    def test_min_len_missing_field(self):
        r = _evaluate_rule(_rule("min_len:$.name=1"), {})
        assert r.passed is False


class TestMaxLen:
    def test_max_len_pass(self):
        r = _evaluate_rule(_rule("max_len:$.items=5"), {"items": [1, 2]})
        assert r.passed is True

    def test_max_len_fail(self):
        r = _evaluate_rule(_rule("max_len:$.items=1"), {"items": [1, 2, 3]})
        assert r.passed is False


class TestMaxVal:
    def test_max_val_pass(self):
        r = _evaluate_rule(_rule("max_val:$.count=10"), {"count": 5})
        assert r.passed is True

    def test_max_val_fail(self):
        r = _evaluate_rule(_rule("max_val:$.count=10"), {"count": 15})
        assert r.passed is False

    def test_max_val_missing_is_ok(self):
        r = _evaluate_rule(_rule("max_val:$.count=10"), {})
        assert r.passed is True


class TestRegexNot:
    def test_clean_string(self):
        r = _evaluate_rule(
            _rule("regex_not:$.text=DROP TABLE"), {"text": "Hello world"}
        )
        assert r.passed is True

    def test_forbidden_pattern(self):
        r = _evaluate_rule(
            _rule("regex_not:$.text=DROP TABLE"), {"text": "DROP TABLE users"}
        )
        assert r.passed is False

    def test_case_insensitive(self):
        r = _evaluate_rule(
            _rule("regex_not:$.text=drop table"), {"text": "DROP TABLE x"}
        )
        assert r.passed is False

    def test_non_string_field(self):
        r = _evaluate_rule(_rule("regex_not:$.val=bad"), {"val": 42})
        assert r.passed is True


class TestAllowed:
    def test_value_in_allowed(self):
        r = _evaluate_rule(_rule("allowed:$.mode=fast,slow,auto"), {"mode": "fast"})
        assert r.passed is True

    def test_value_not_in_allowed(self):
        r = _evaluate_rule(_rule("allowed:$.mode=fast,slow"), {"mode": "turbo"})
        assert r.passed is False


class TestEachHas:
    def test_all_have_field(self):
        items = [{"name": "a"}, {"name": "b"}]
        r = _evaluate_rule(_rule("each_has:$.items=name"), {"items": items})
        assert r.passed is True

    def test_missing_field_in_item(self):
        items = [{"name": "a"}, {"other": "b"}]
        r = _evaluate_rule(_rule("each_has:$.items=name"), {"items": items})
        assert r.passed is False

    def test_not_array(self):
        r = _evaluate_rule(_rule("each_has:$.items=name"), {"items": "string"})
        assert r.passed is False


class TestNoneMatch:
    def test_no_match(self):
        items = ["safe", "ok"]
        r = _evaluate_rule(_rule("none_match:$.items=forbidden"), {"items": items})
        assert r.passed is True

    def test_has_match(self):
        items = ["safe", "forbidden_value"]
        r = _evaluate_rule(_rule("none_match:$.items=forbidden"), {"items": items})
        assert r.passed is False

    def test_not_array(self):
        r = _evaluate_rule(_rule("none_match:$.items=bad"), {"items": "string"})
        assert r.passed is True


class TestUnknownExpression:
    def test_unknown_fails(self):
        r = _evaluate_rule(_rule("foobar:$.x"), {"x": 1})
        assert r.passed is False
        assert "unknown rule expression" in r.detail


# ── PolicyEngine loading logic ──────────────────────────────────────


class TestPolicyEngineLoading:
    async def test_cache_hit_returns_cached(self, fake_repo, fake_cache, circuit_breaker):
        """When cache has rules, repository is not called."""
        rule = _rule("exists:$.name")
        await fake_cache.set_rules(ValidationPhase.REQUEST, [rule])

        engine = PolicyEngine(fake_repo, fake_cache, circuit_breaker)
        report = await engine.evaluate(ValidationPhase.REQUEST, {"name": "test"})
        assert report.passed_count == 1
        # Repo was never seeded, so if cache missed it would return 0 rules
        assert len(report.results) == 1

    async def test_cache_miss_fetches_from_repo(self, fake_repo, fake_cache, circuit_breaker):
        """When cache is empty, rules come from repository and get cached."""
        rule = _rule("exists:$.name")
        fake_repo.seed(rule)

        engine = PolicyEngine(fake_repo, fake_cache, circuit_breaker)
        report = await engine.evaluate(ValidationPhase.REQUEST, {"name": "test"})
        assert report.passed_count == 1

        # Verify cache was populated
        cached = await fake_cache.get_rules(ValidationPhase.REQUEST)
        assert cached is not None
        assert len(cached) == 1

    async def test_both_unavailable_raises(self, fake_cache, circuit_breaker):
        """When cache is empty and repo raises, RuntimeError is raised."""

        class FailingRepo:
            async def get_rules(self, phase):
                raise ConnectionError("DB down")

        engine = PolicyEngine(FailingRepo(), fake_cache, circuit_breaker)
        with pytest.raises(RuntimeError, match="no_policies_available"):
            await engine.evaluate(ValidationPhase.REQUEST, {"name": "test"})

    async def test_circuit_breaker_open_raises(self, fake_cache):
        """When circuit breaker is OPEN, RuntimeError is raised immediately."""

        class FailingRepo:
            async def get_rules(self, phase):
                raise ConnectionError("DB down")

        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=999)
        engine = PolicyEngine(FailingRepo(), fake_cache, cb)

        # First failure opens the circuit
        with pytest.raises(RuntimeError):
            await engine.evaluate(ValidationPhase.REQUEST, {})

        assert cb.state == CircuitState.OPEN

        # Second call is rejected immediately
        with pytest.raises(RuntimeError, match="circuit breaker OPEN"):
            await engine.evaluate(ValidationPhase.REQUEST, {})

    async def test_threat_rules_filtered_from_evaluate(self, fake_repo, fake_cache, circuit_breaker):
        """THREAT category rules are excluded from compliance evaluation."""
        format_rule = _rule("exists:$.name")
        threat_rule = PolicyRule(
            id=uuid4(),
            name="threat_rule",
            phase=ValidationPhase.ARCHITECTURE,
            category=PolicyCategory.THREAT,
            severity=SeverityLevel.HIGH,
            rule_expression="exists:$.attack_surface",
            description="threat matrix entry",
        )
        fake_repo.seed(format_rule)
        fake_repo.seed(threat_rule)

        engine = PolicyEngine(fake_repo, fake_cache, circuit_breaker)
        # Evaluate ARCHITECTURE (both rules are REQUEST phase for format_rule,
        # but threat_rule is ARCHITECTURE). Only the threat_rule is ARCHITECTURE.
        report = await engine.evaluate(ValidationPhase.ARCHITECTURE, {"attack_surface": "web"})
        # threat_rule should be filtered out from compliance results
        assert all(r.rule_name != "threat_rule" for r in report.results)

    async def test_get_threat_matrix(self, fake_repo, fake_cache, circuit_breaker):
        """get_threat_matrix returns only THREAT category rules."""
        threat_rule = PolicyRule(
            id=uuid4(),
            name="threat_rule",
            phase=ValidationPhase.ARCHITECTURE,
            category=PolicyCategory.THREAT,
            severity=SeverityLevel.HIGH,
            rule_expression="exists:$.x",
            description="threat",
        )
        normal_rule = PolicyRule(
            id=uuid4(),
            name="normal_rule",
            phase=ValidationPhase.ARCHITECTURE,
            category=PolicyCategory.FORMAT,
            severity=SeverityLevel.LOW,
            rule_expression="exists:$.y",
            description="format",
        )
        fake_repo.seed(threat_rule)
        fake_repo.seed(normal_rule)

        engine = PolicyEngine(fake_repo, fake_cache, circuit_breaker)
        matrix = await engine.get_threat_matrix()
        assert len(matrix) == 1
        assert matrix[0].name == "threat_rule"
