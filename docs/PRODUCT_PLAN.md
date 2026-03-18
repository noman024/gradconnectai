# GradConnectAI Product Plan (Code-Synced)

Last verified against repository code on 18-Mar-2026.

## Product scope

GradConnectAI helps Master's, PhD, and Postdoc applicants:

1. Create a profile from CV text or PDF.
2. Discover potential supervisors from public web pages.
3. Rank supervisors by semantic fit and opportunity score.
4. Generate personalized email drafts for student review and manual sending.

## Expected end-to-end workflow

1. **Student profile ingestion**
   - User uploads a CV PDF or pastes CV text.
   - System validates input, stores student profile, and extracts research topics/skills.
2. **Student understanding and query planning**
   - System converts CV signal into structured interests (topics, methods, domains, preferences).
   - System constructs SEO-friendly search intents/keywords for external discovery.
3. **Search and URL collection (planned expansion)**
   - Run targeted searches on Google and LinkedIn (including LinkedIn posts) using generated queries.
   - Collect top links/posts and prioritize likely supervisor/opportunity sources.
4. **Crawl and content normalization**
   - Crawl shortlisted pages and normalize content into LLM-ready markdown/text.
5. **LLM extraction and evidence gating**
   - Use Qwen (Ollama/vLLM via OpenAI-compatible API) to extract professor candidates and opportunity signals.
   - Enforce evidence gates (name + email/profile_url) before persistence.
6. **Scoring and ranking**
   - Build embeddings and compute semantic fit against student profile.
   - Combine fit score with opportunity score for final ranking.
7. **User-facing output**
   - Show ranked supervisors with details in UI.
   - Generate personalized outreach draft for user review and manual sending.

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
- [x] Google search ingestion MVP (`POST /api/v1/discovery/google-search`) for top-link collection + dedupe + scoring.
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

- [x] Add discovery dry-run mode (return candidates/evidence without DB writes).
- [x] Persist richer evidence snippets/selectors consistently for each accepted field.
- [x] Add unit tests with saved fixtures for evidence gate logic.
- [x] Add retention/cleanup jobs for source documents and evidence artifacts.

### Product capabilities

- [x] Build CV-driven query planner to generate SEO-friendly Google/LinkedIn search keywords.
- [ ] Implement browser-based Google search ingestion (top links collection + dedupe + scoring). (MVP HTTP ingestion exists)
- [ ] Implement LinkedIn post/profile discovery with session management and recency weighting.
- [x] Add URL prioritization layer before crawl (source quality + relevance + freshness).
- [ ] Expand opportunity extraction into explicit structured opportunities + explanations in UI.

### Workflow sync checklist (expected vs implemented)

- [x] CV upload/paste -> topic extraction -> student profile persistence.
- [x] CV-derived query generation for Google/LinkedIn discovery.
- [ ] Automated Google + LinkedIn search harvesting of top links/posts.
- [x] Crawl + normalize + Qwen extraction from seed URLs.
- [x] Evidence-gated acceptance before professor persistence.
- [x] Semantic + opportunity ranking in matches endpoint.
- [x] Personalized draft generation in email endpoint.

### Security and accounts

- [ ] Add user model + Google OAuth login.
- [ ] Enforce per-user authorization across student/match/draft data.
- [ ] Move from IP-only rate limits toward per-user quotas.

### Deployment and operations

- [ ] Add Dockerfiles and Docker Compose for frontend, backend, worker, Postgres, and model services.
- [ ] Introduce migration workflow (Alembic) for production-safe schema changes.
- [x] Add CI (lint/tests/type checks) and initial E2E test coverage.

## Definition of done for production-ready MVP

- Authenticated multi-user access with strict data isolation.
- Evidence-backed discovery with automated tests and measurable quality checks.
- Async job workers for discovery/refresh to keep API responsive.
- Reproducible containerized deployment and automated CI checks.


