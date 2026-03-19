-- GradConnectAI — PostgreSQL schema with pgvector
-- Run after: CREATE EXTENSION IF NOT EXISTS vector;

-- Professors (discovered and optionally re-verified)
CREATE TABLE IF NOT EXISTS professors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    university TEXT NOT NULL,
    country TEXT,
    region TEXT,
    email TEXT,
    research_topics JSONB DEFAULT '[]',
    lab_url TEXT,
    lab_focus TEXT,
    opportunity_score FLOAT DEFAULT 0.5 CHECK (opportunity_score >= 0 AND opportunity_score <= 1),
    embedding vector(384),  -- matches all-MiniLM-L6-v2 output dimension
    embedding_model_version TEXT,
    last_checked TIMESTAMPTZ,
    active_flag BOOLEAN DEFAULT false,
    sources JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_professors_embedding ON professors
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_professors_last_checked ON professors (last_checked);
CREATE INDEX IF NOT EXISTS idx_professors_active ON professors (active_flag) WHERE active_flag = true;

-- Professor history for auditing (previous values when updated)
CREATE TABLE IF NOT EXISTS professor_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    professor_id UUID NOT NULL REFERENCES professors(id) ON DELETE CASCADE,
    name TEXT,
    university TEXT,
    country TEXT,
    region TEXT,
    email TEXT,
    research_topics JSONB,
    lab_url TEXT,
    sources JSONB,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_professor_snapshots_professor_id ON professor_snapshots (professor_id);
CREATE INDEX IF NOT EXISTS idx_professor_snapshots_valid ON professor_snapshots (valid_from, valid_to);

-- Opportunities (Master / PhD / Postdoc)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'opportunity_type') THEN
        CREATE TYPE opportunity_type AS ENUM ('master', 'phd', 'postdoc');
    END IF;
END$$;

CREATE TABLE IF NOT EXISTS opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    professor_id UUID NOT NULL REFERENCES professors(id) ON DELETE CASCADE,
    type opportunity_type NOT NULL,
    funding TEXT,  -- 'Fully funded', 'Partial', 'Unknown'
    deadline DATE,
    source TEXT,
    expired BOOLEAN DEFAULT false,
    valid_until DATE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_opportunities_professor ON opportunities (professor_id);
CREATE INDEX IF NOT EXISTS idx_opportunities_expired ON opportunities (expired) WHERE expired = false;

-- Students (profile + preferences + embedding)
-- preferences shape: { "countries": [], "universities": [], "fields": [] }
CREATE TABLE IF NOT EXISTS students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    research_topics JSONB DEFAULT '[]',
    embedding vector(384),
    embedding_model_version TEXT,
    cv_file TEXT,
    experience_snippet TEXT,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_students_embedding ON students
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Matches (student–professor with scores)
CREATE TABLE IF NOT EXISTS matches (
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    professor_id UUID NOT NULL REFERENCES professors(id) ON DELETE CASCADE,
    score FLOAT NOT NULL CHECK (score >= 0 AND score <= 1),
    opportunity_score FLOAT NOT NULL CHECK (opportunity_score >= 0 AND opportunity_score <= 1),
    final_rank FLOAT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (student_id, professor_id)
);

CREATE INDEX IF NOT EXISTS idx_matches_student ON matches (student_id);
CREATE INDEX IF NOT EXISTS idx_matches_final_rank ON matches (student_id, final_rank DESC);

-- Email drafts (for retention and resend)
CREATE TABLE IF NOT EXISTS email_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    professor_id UUID NOT NULL REFERENCES professors(id) ON DELETE CASCADE,
    subject TEXT,
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_email_drafts_student ON email_drafts (student_id);

-- Audit log (who did what, when)
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log (created_at);

-- =========================================================
-- Evidence-gated discovery (productionization)
-- =========================================================

-- Source documents fetched and rendered for extraction (auditable)
CREATE TABLE IF NOT EXISTS source_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    content_hash TEXT,
    status_code INT,
    robots_allowed BOOLEAN,
    content_type TEXT,
    -- Store a bounded copy of normalized text/markdown for debugging & evidence matching.
    -- (For large pages, store truncated content; full storage can be moved to object storage later.)
    content_text TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_source_documents_url ON source_documents (url);
CREATE INDEX IF NOT EXISTS idx_source_documents_fetched_at ON source_documents (fetched_at DESC);

-- Extraction runs (LLM prompts, versions, and outcomes)
CREATE TABLE IF NOT EXISTS extraction_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_document_id UUID REFERENCES source_documents(id) ON DELETE CASCADE,
    extractor TEXT NOT NULL, -- e.g. "qwen_professor_extract"
    llm_model TEXT,
    prompt_version TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    success BOOLEAN DEFAULT false,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_extraction_runs_source_document_id ON extraction_runs (source_document_id);
CREATE INDEX IF NOT EXISTS idx_extraction_runs_started_at ON extraction_runs (started_at DESC);

-- Evidence proving why a professor record was created/updated
CREATE TABLE IF NOT EXISTS professor_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    professor_id UUID NOT NULL REFERENCES professors(id) ON DELETE CASCADE,
    source_document_id UUID REFERENCES source_documents(id) ON DELETE SET NULL,
    extraction_run_id UUID REFERENCES extraction_runs(id) ON DELETE SET NULL,
    url TEXT NOT NULL,
    evidence_type TEXT NOT NULL, -- "name" | "email" | "profile_url" | "obfuscated_email"
    evidence_value TEXT,         -- the exact extracted value (e.g. email, profile url)
    raw_match TEXT,              -- raw text matched before normalization/decoding (if any)
    snippet TEXT,                -- surrounding snippet for human audit
    selector TEXT,               -- optional DOM selector/path when available
    confidence FLOAT DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_professor_evidence_professor_id ON professor_evidence (professor_id);
CREATE INDEX IF NOT EXISTS idx_professor_evidence_created_at ON professor_evidence (created_at DESC);
