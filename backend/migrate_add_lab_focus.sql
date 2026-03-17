-- Migration: Add lab_focus, opportunity_score (professors) and experience_snippet (students)
-- Run if your tables were created before these columns existed.
-- Usage: cd backend && python run_migrate.py

ALTER TABLE professors ADD COLUMN IF NOT EXISTS lab_focus TEXT;
ALTER TABLE professors ADD COLUMN IF NOT EXISTS opportunity_score FLOAT DEFAULT 0.5;
ALTER TABLE students ADD COLUMN IF NOT EXISTS experience_snippet TEXT;
