"""FastAPI dependency injection wiring."""
from __future__ import annotations

from functools import lru_cache

import asyncpg
import redis.asyncio as redis

from mval.arbiter.arbiter import ValidationArbiter
from mval.config import settings
from mval.gateway.gateway import ValidationGateway
from mval.logging.audit import AuditLogger
from mval.policy.cache import PolicyCache
from mval.policy.circuit_breaker import CircuitBreaker
from mval.policy.engine import PolicyEngine
from mval.policy.repository import PolicyRepository
from mval.validators.architecture_validator import ArchitectureValidator
from mval.validators.request_validator import RequestValidator

# ── Singletons (created at app startup via lifespan) ──

_pg_pool: asyncpg.Pool | None = None
_redis_client: redis.Redis | None = None


async def init_resources() -> None:
    global _pg_pool, _redis_client
    _pg_pool = await asyncpg.create_pool(settings.postgres_dsn, min_size=2, max_size=10)
    _redis_client = redis.from_url(settings.redis_url, decode_responses=True)


async def close_resources() -> None:
    global _pg_pool, _redis_client
    if _pg_pool:
        await _pg_pool.close()
    if _redis_client:
        await _redis_client.aclose()


# ── Dependency providers ──


def get_policy_repository() -> PolicyRepository:
    assert _pg_pool is not None, "PostgreSQL pool not initialized"
    return PolicyRepository(_pg_pool)


def get_policy_cache() -> PolicyCache:
    assert _redis_client is not None, "Redis client not initialized"
    return PolicyCache(_redis_client, ttl_seconds=settings.policy_cache_ttl_seconds)


@lru_cache
def _circuit_breaker() -> CircuitBreaker:
    return CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)


def get_policy_engine() -> PolicyEngine:
    return PolicyEngine(
        repository=get_policy_repository(),
        cache=get_policy_cache(),
        circuit_breaker=_circuit_breaker(),
    )


@lru_cache
def _audit_logger() -> AuditLogger:
    return AuditLogger()


@lru_cache
def _arbiter() -> ValidationArbiter:
    return ValidationArbiter()


def get_gateway() -> ValidationGateway:
    engine = get_policy_engine()
    audit = _audit_logger()
    arbiter = _arbiter()

    request_validator = RequestValidator(engine, arbiter, audit)
    architecture_validator = ArchitectureValidator(engine, arbiter, audit)

    return ValidationGateway(request_validator, architecture_validator, audit)
