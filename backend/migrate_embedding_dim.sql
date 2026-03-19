-- Migration: Change embedding vector dimension from 768 to 384
-- This matches all-MiniLM-L6-v2 output dimension and eliminates zero-padding.
-- NOTE: Existing embeddings will be dropped since they were zero-padded and invalid.

BEGIN;

-- Drop indexes that reference the old vector type
DROP INDEX IF EXISTS idx_professors_embedding;
DROP INDEX IF EXISTS idx_students_embedding;

-- Alter columns to the correct dimension
ALTER TABLE professors ALTER COLUMN embedding TYPE vector(384);
ALTER TABLE students   ALTER COLUMN embedding TYPE vector(384);

-- Recreate indexes with new dimension
CREATE INDEX IF NOT EXISTS idx_professors_embedding ON professors
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_students_embedding ON students
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Null out existing (incorrectly padded) embeddings so they get regenerated
UPDATE professors SET embedding = NULL WHERE embedding IS NOT NULL;
UPDATE students   SET embedding = NULL WHERE embedding IS NOT NULL;

COMMIT;
