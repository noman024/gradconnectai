# GradConnectAI Product Plan (Code-Synced)

Last verified against repository code on 18-Mar-2026.

## Product scope

GradConnectAI helps Master's, PhD, and Postdoc applicants:

1. Create a profile from CV text or PDF.
2. Discover potential supervisors from public web pages.
3. Rank supervisors by semantic fit and opportunity score.
4. Generate personalized email drafts for student review and manual sending.

## Current architecture

- Frontend: Next.js App Router dashboard (`/profile`, `/matches`, `/email/[professorId]`).
- Backend: FastAPI API + modular services (portfolio, discovery, matching, email generation).
- Data: PostgreSQL + pgvector via SQLAlchemy models.
- AI: OpenAI-compatible LLM endpoint (Ollama/vLLM) + sentence-transformers embeddings.

## What is implemented

### Core user flow

- [x] Profile creation from text (`POST /api/v1/students`) and PDF upload (`POST /api/v1/students/upload`).
- [x] Topic extraction + embedding generation for student profiles.
- [x] Discovery endpoint (`POST /api/v1/discovery/run`) using Crawl4AI markdown + LLM extraction.
- [x] Evidence-gated extraction (name + email/profile_url checks before persistence).
- [x] Matching endpoint (`GET /api/v1/matches`) using semantic similarity + `opportunity_score`.
- [x] Email draft generation endpoint (`POST /api/v1/email-drafts/generate`).
- [x] Frontend screens wired to backend APIs with loading/error handling.

### Data model and governance

- [x] Evidence tables present and used: `source_documents`, `extraction_runs`, `professor_evidence`.
- [x] Audit logging for key actions and GDPR endpoints (export/delete student data).
- [x] Admin inspection routes (development-only) for stats, snapshots, opportunities, and audit logs.

### Configuration and runtime controls

- [x] Unified env template in `config/app.env.example` (backend + frontend).
- [x] Backend config loads only `config/app.env`.
- [x] Frontend reads `config/app.env` values (notably `NEXT_PUBLIC_API_BASE`) via `next.config.js`.
- [x] Tunable LLM and crawler limits exposed via env variables.

## Incomplete roadmap (next priority)

### Correctness and quality

- [ ] Add discovery dry-run mode (return candidates/evidence without DB writes).
- [ ] Persist richer evidence snippets/selectors consistently for each accepted field.
- [ ] Add unit tests with saved fixtures for evidence gate logic.
- [ ] Add retention/cleanup jobs for source documents and evidence artifacts.

### Product capabilities

- [ ] Build "own SERP" query planner and browser-based Google search ingestion.
- [ ] Add LinkedIn post/profile discovery with session management and recency weighting.
- [ ] Expand opportunity extraction into explicit structured opportunities + explanations in UI.

### Security and accounts

- [ ] Add user model + Google OAuth login.
- [ ] Enforce per-user authorization across student/match/draft data.
- [ ] Move from IP-only rate limits toward per-user quotas.

### Deployment and operations

- [ ] Add Dockerfiles and Docker Compose for frontend, backend, worker, Postgres, and model services.
- [ ] Introduce migration workflow (Alembic) for production-safe schema changes.
- [ ] Add CI (lint/tests/type checks) and initial E2E test coverage.

## Definition of done for production-ready MVP

- Authenticated multi-user access with strict data isolation.
- Evidence-backed discovery with automated tests and measurable quality checks.
- Async job workers for discovery/refresh to keep API responsive.
- Reproducible containerized deployment and automated CI checks.


