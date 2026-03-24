"""Tests for /policies CRUD API router."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mval.domain.enums import PolicyCategory, SeverityLevel, ValidationPhase
from mval.domain.models import PolicyRule, PolicyRuleCreate
from mval.policy.router import router
from mval.dependencies import get_policy_repository, get_policy_cache


# ── In-memory fakes (local copies to avoid conftest import issues) ───


class _FakeRepo:
    def __init__(self):
        self._store: dict[UUID, PolicyRule] = {}

    async def get_rules(self, phase):
        return [r for r in self._store.values() if r.phase == phase and r.enabled]

    async def get_rule(self, rule_id):
        return self._store.get(rule_id)

    async def create_rule(self, rule: PolicyRuleCreate):
        now = datetime.now(timezone.utc)
        new = PolicyRule(id=uuid4(), **rule.model_dump(), created_at=now, updated_at=now)
        self._store[new.id] = new
        return new

    async def update_rule(self, rule_id, rule: PolicyRuleCreate):
        if rule_id not in self._store:
            return None
        now = datetime.now(timezone.utc)
        updated = PolicyRule(
            id=rule_id, **rule.model_dump(),
            created_at=self._store[rule_id].created_at, updated_at=now,
        )
        self._store[rule_id] = updated
        return updated

    async def delete_rule(self, rule_id):
        if rule_id in self._store:
            del self._store[rule_id]
            return True
        return False

    async def list_rules(self):
        return list(self._store.values())


class _FakeCache:
    def __init__(self):
        self._store: dict[str, list] = {}

    async def get_rules(self, phase):
        return self._store.get(phase.value)

    async def set_rules(self, phase, rules):
        self._store[phase.value] = rules

    async def invalidate(self, phase=None):
        if phase:
            self._store.pop(phase.value, None)
        else:
            self._store.clear()


# ── App setup ────────────────────────────────────────────────────────

_fake_repo = _FakeRepo()
_fake_cache = _FakeCache()

app = FastAPI()
app.include_router(router)
app.dependency_overrides[get_policy_repository] = lambda: _fake_repo
app.dependency_overrides[get_policy_cache] = lambda: _fake_cache

client = TestClient(app)


def _rule_payload(
    name: str = "test_rule",
    phase: str = "REQUEST",
    category: str = "FORMAT",
    severity: str = "MEDIUM",
    expression: str = "exists:$.field",
    description: str = "test rule",
) -> dict:
    return {
        "name": name,
        "phase": phase,
        "category": category,
        "severity": severity,
        "rule_expression": expression,
        "description": description,
        "enabled": True,
    }


class TestCreateRule:
    def setup_method(self):
        _fake_repo._store.clear()
        _fake_cache._store.clear()

    def test_create_rule_returns_201(self):
        resp = client.post("/policies/", json=_rule_payload())
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test_rule"
        assert "id" in data

    def test_create_rule_persists(self):
        client.post("/policies/", json=_rule_payload(name="persisted"))
        resp = client.get("/policies/")
        names = [r["name"] for r in resp.json()]
        assert "persisted" in names


class TestListRules:
    def setup_method(self):
        _fake_repo._store.clear()
        _fake_cache._store.clear()

    def test_list_empty(self):
        resp = client.get("/policies/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_after_create(self):
        client.post("/policies/", json=_rule_payload(name="rule1"))
        client.post("/policies/", json=_rule_payload(name="rule2"))
        resp = client.get("/policies/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestGetRule:
    def setup_method(self):
        _fake_repo._store.clear()
        _fake_cache._store.clear()

    def test_get_existing_rule(self):
        create_resp = client.post("/policies/", json=_rule_payload())
        rule_id = create_resp.json()["id"]
        resp = client.get(f"/policies/{rule_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == rule_id

    def test_get_nonexistent_rule_returns_404(self):
        fake_id = str(uuid4())
        resp = client.get(f"/policies/{fake_id}")
        assert resp.status_code == 404


class TestUpdateRule:
    def setup_method(self):
        _fake_repo._store.clear()
        _fake_cache._store.clear()

    def test_update_existing_rule(self):
        create_resp = client.post("/policies/", json=_rule_payload(name="original"))
        rule_id = create_resp.json()["id"]

        updated_payload = _rule_payload(name="updated")
        resp = client.put(f"/policies/{rule_id}", json=updated_payload)
        assert resp.status_code == 200
        assert resp.json()["name"] == "updated"

    def test_update_nonexistent_rule_returns_404(self):
        fake_id = str(uuid4())
        resp = client.put(f"/policies/{fake_id}", json=_rule_payload())
        assert resp.status_code == 404


class TestDeleteRule:
    def setup_method(self):
        _fake_repo._store.clear()
        _fake_cache._store.clear()

    def test_delete_existing_rule(self):
        create_resp = client.post("/policies/", json=_rule_payload())
        rule_id = create_resp.json()["id"]

        resp = client.delete(f"/policies/{rule_id}")
        assert resp.status_code == 204

        get_resp = client.get(f"/policies/{rule_id}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_rule_returns_404(self):
        fake_id = str(uuid4())
        resp = client.delete(f"/policies/{fake_id}")
        assert resp.status_code == 404
