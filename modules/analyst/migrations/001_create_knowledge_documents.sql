CREATE TABLE IF NOT EXISTS knowledge_documents (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type       TEXT NOT NULL,
    source_id         TEXT NOT NULL,
    title             TEXT NOT NULL,
    content           TEXT NOT NULL,
    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding         DOUBLE PRECISION[],
    embedding_model   TEXT,
    embedding_dim     INTEGER,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_type, source_id)
);

CREATE INDEX IF NOT EXISTS idx_kd_source_type ON knowledge_documents (source_type);
CREATE INDEX IF NOT EXISTS idx_kd_source_id ON knowledge_documents (source_id);
CREATE INDEX IF NOT EXISTS idx_kd_metadata_gin ON knowledge_documents USING GIN (metadata);

-- Для keyword fallback поиска (без векторного индекса):
CREATE INDEX IF NOT EXISTS idx_kd_content_tsv
ON knowledge_documents USING GIN (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, '')));

