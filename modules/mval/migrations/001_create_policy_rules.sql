CREATE TABLE IF NOT EXISTS policy_rules (
    id              UUID PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    phase           TEXT NOT NULL CHECK (phase IN ('REQUEST', 'ARCHITECTURE')),
    category        TEXT NOT NULL CHECK (category IN ('FORMAT', 'SECURITY', 'COMPLIANCE', 'THREAT')),
    severity        TEXT NOT NULL CHECK (severity IN ('INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    rule_expression TEXT NOT NULL,
    expected_value  TEXT,
    description     TEXT NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_policy_rules_phase ON policy_rules (phase) WHERE enabled = TRUE;
CREATE INDEX IF NOT EXISTS idx_policy_rules_category ON policy_rules (category) WHERE enabled = TRUE;
