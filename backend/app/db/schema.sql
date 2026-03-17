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
    embedding vector(768),  -- adjust dimension to match your embedding model
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
CREATE TYPE opportunity_type AS ENUM ('master', 'phd', 'postdoc');

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
    embedding vector(768),
    embedding_model_version TEXT,
    cv_file TEXT,
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
