from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from mval.domain.models import PolicyRule, PolicyRuleCreate
from mval.dependencies import get_policy_cache, get_policy_repository

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("/", response_model=list[PolicyRule])
async def list_rules(
    repo=Depends(get_policy_repository),
):
    return await repo.list_rules()


@router.get("/{rule_id}", response_model=PolicyRule)
async def get_rule(
    rule_id: UUID,
    repo=Depends(get_policy_repository),
):
    rule = await repo.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.post("/", response_model=PolicyRule, status_code=201)
async def create_rule(
    body: PolicyRuleCreate,
    repo=Depends(get_policy_repository),
    cache=Depends(get_policy_cache),
):
    rule = await repo.create_rule(body)
    await cache.invalidate(rule.phase)
    return rule


@router.put("/{rule_id}", response_model=PolicyRule)
async def update_rule(
    rule_id: UUID,
    body: PolicyRuleCreate,
    repo=Depends(get_policy_repository),
    cache=Depends(get_policy_cache),
):
    rule = await repo.update_rule(rule_id, body)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await cache.invalidate(rule.phase)
    return rule


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: UUID,
    repo=Depends(get_policy_repository),
    cache=Depends(get_policy_cache),
):
    deleted = await repo.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    await cache.invalidate()
