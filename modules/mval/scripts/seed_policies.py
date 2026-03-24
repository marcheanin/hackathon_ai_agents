#!/usr/bin/env python3
"""Seed БДвал with test policy rules.

Usage:
    python scripts/seed_policies.py [--db-url postgresql://mval:mval_secret@localhost:5432/mval]
"""
from __future__ import annotations

import argparse
import asyncio
import sys

import asyncpg

SEED_RULES = [
    # ── REQUEST phase: FORMAT ─────────────────────────────────
    {
        "name": "req_has_objective",
        "phase": "REQUEST",
        "category": "FORMAT",
        "severity": "CRITICAL",
        "rule_expression": "exists:$.objective",
        "description": "Every request must state its objective",
    },
    {
        "name": "req_has_constraints",
        "phase": "REQUEST",
        "category": "FORMAT",
        "severity": "HIGH",
        "rule_expression": "min_len:$.constraints=1",
        "description": "At least one constraint required",
    },
    {
        "name": "req_objective_length",
        "phase": "REQUEST",
        "category": "FORMAT",
        "severity": "MEDIUM",
        "rule_expression": "max_len:$.objective=2000",
        "description": "Objective must not exceed 2000 characters",
    },
    {
        "name": "req_has_domain",
        "phase": "REQUEST",
        "category": "FORMAT",
        "severity": "HIGH",
        "rule_expression": "exists:$.domain",
        "description": "Domain must be specified",
    },
    # ── REQUEST phase: SECURITY ───────────────────────────────
    {
        "name": "req_no_injection_patterns",
        "phase": "REQUEST",
        "category": "SECURITY",
        "severity": "CRITICAL",
        "rule_expression": "regex_not:$.objective=(ignore|disregard|forget).*instructions",
        "description": "Block prompt injection attempts in objective",
    },
    # ── REQUEST phase: COMPLIANCE ─────────────────────────────
    {
        "name": "req_budget_positive",
        "phase": "REQUEST",
        "category": "COMPLIANCE",
        "severity": "MEDIUM",
        "rule_expression": "max_val:$.budget=1000000",
        "description": "Budget, if provided, must be <= 1,000,000",
    },
    # ── ARCHITECTURE phase: FORMAT ────────────────────────────
    {
        "name": "arch_has_components",
        "phase": "ARCHITECTURE",
        "category": "FORMAT",
        "severity": "CRITICAL",
        "rule_expression": "min_len:$.components=1",
        "description": "Architecture must define at least one component",
    },
    {
        "name": "arch_has_data_flow",
        "phase": "ARCHITECTURE",
        "category": "FORMAT",
        "severity": "HIGH",
        "rule_expression": "min_len:$.data_flows=1",
        "description": "Data flow between components must be defined",
    },
    {
        "name": "arch_max_components",
        "phase": "ARCHITECTURE",
        "category": "COMPLIANCE",
        "severity": "MEDIUM",
        "rule_expression": "max_len:$.components=20",
        "description": "Prototype limit: max 20 components",
    },
    # ── ARCHITECTURE phase: SECURITY ──────────────────────────
    {
        "name": "arch_has_auth",
        "phase": "ARCHITECTURE",
        "category": "SECURITY",
        "severity": "CRITICAL",
        "rule_expression": "each_has:$.components=auth_mechanism",
        "description": "Each component must specify an auth mechanism",
    },
    {
        "name": "arch_no_hardcoded_secrets",
        "phase": "ARCHITECTURE",
        "category": "SECURITY",
        "severity": "CRITICAL",
        "rule_expression": "none_match:$.components=(password|secret|api_key)\\s*[:=]\\s*[\"'][^\"']+[\"']",
        "description": "No hardcoded credentials in component configs",
    },
    {
        "name": "arch_has_error_handling",
        "phase": "ARCHITECTURE",
        "category": "COMPLIANCE",
        "severity": "HIGH",
        "rule_expression": "each_has:$.components=error_handling",
        "description": "Each component must define error handling strategy",
    },
    {
        "name": "arch_encryption_at_rest",
        "phase": "ARCHITECTURE",
        "category": "SECURITY",
        "severity": "HIGH",
        "rule_expression": "each_has:$.components=encryption",
        "description": "Components storing data must declare encryption",
    },
    # ── ARCHITECTURE phase: THREAT (for Red Teaming) ──────────
    {
        "name": "threat_privilege_escalation",
        "phase": "ARCHITECTURE",
        "category": "THREAT",
        "severity": "CRITICAL",
        "rule_expression": "Evaluate if any component allows lateral movement or privilege escalation",
        "description": "Check for privilege escalation paths between components",
    },
    {
        "name": "threat_data_exfiltration",
        "phase": "ARCHITECTURE",
        "category": "THREAT",
        "severity": "CRITICAL",
        "rule_expression": "Evaluate if data can leave the system boundary without controls",
        "description": "Check for data exfiltration vectors",
    },
    {
        "name": "threat_dos_resilience",
        "phase": "ARCHITECTURE",
        "category": "THREAT",
        "severity": "HIGH",
        "rule_expression": "Evaluate if components have rate limiting and resource caps",
        "description": "DoS resilience assessment",
    },
    {
        "name": "threat_injection_surface",
        "phase": "ARCHITECTURE",
        "category": "THREAT",
        "severity": "HIGH",
        "rule_expression": "Evaluate all input surfaces for injection vulnerabilities (SQL, NoSQL, prompt)",
        "description": "Injection attack surface analysis",
    },
    {
        "name": "threat_dependency_supply_chain",
        "phase": "ARCHITECTURE",
        "category": "THREAT",
        "severity": "MEDIUM",
        "rule_expression": "Evaluate third-party dependencies for known risk patterns",
        "description": "Supply chain attack surface",
    },
]


async def seed(db_url: str) -> None:
    conn = await asyncpg.connect(db_url)
    try:
        for rule in SEED_RULES:
            await conn.execute(
                """
                INSERT INTO policy_rules
                    (id, name, phase, category, severity, rule_expression,
                     expected_value, description, enabled, created_at, updated_at)
                VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, NULL, $6, TRUE, NOW(), NOW())
                ON CONFLICT (name) DO UPDATE SET
                    phase = EXCLUDED.phase,
                    category = EXCLUDED.category,
                    severity = EXCLUDED.severity,
                    rule_expression = EXCLUDED.rule_expression,
                    description = EXCLUDED.description,
                    updated_at = NOW()
                """,
                rule["name"],
                rule["phase"],
                rule["category"],
                rule["severity"],
                rule["rule_expression"],
                rule["description"],
            )
            print(f"  [OK] {rule['name']}")
    finally:
        await conn.close()
    print(f"\nSeeded {len(SEED_RULES)} policy rules.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed БДвал with test policies")
    parser.add_argument(
        "--db-url",
        default="postgresql://mval:mval_secret@localhost:5432/mval",
        help="PostgreSQL connection URL",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.db_url))


if __name__ == "__main__":
    main()
