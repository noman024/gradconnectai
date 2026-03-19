# GradConnectAI Product Plan (Code-Synced)

Last verified against repository code on 19-Mar-2026.

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
3. **Search and URL collection**
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
- [x] Browser-based Google ingestion MVP (`POST /api/v1/discovery/google-search-browser`) for top-link collection + dedupe + scoring.
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
- [x] Implement browser-based Google search ingestion (top links collection + dedupe + scoring). (MVP endpoint)
- [x] Implement LinkedIn post/profile discovery with session management and recency weighting. (MVP endpoint)
- [x] Add URL prioritization layer before crawl (source quality + relevance + freshness).
- [x] Expand opportunity extraction into explicit structured opportunities + explanations in UI. (MVP backend + matches UI)

### Workflow sync checklist (expected vs implemented)

- [x] CV upload/paste -> topic extraction -> student profile persistence.
- [x] CV-derived query generation for Google/LinkedIn discovery.
- [x] Automated Google + LinkedIn search harvesting of top links/posts. (MVP integrated harvester endpoint)
- [x] Crawl + normalize + Qwen extraction from seed URLs.
- [x] Evidence-gated acceptance before professor persistence.
- [x] Semantic + opportunity ranking in matches endpoint.
- [x] Personalized draft generation in email endpoint.

### Security and accounts

- [ ] Add user model + Google OAuth login.
- [ ] Enforce per-user authorization across student/match/draft data.
- [ ] Move from IP-only rate limits toward per-user quotas.

### Deployment and operations

- [x] Add Dockerfiles and Docker Compose for frontend, backend, Postgres (pgvector).
- [ ] Introduce migration workflow (Alembic) for production-safe schema changes.
- [x] Add CI (lint/tests/type checks) and smoke test coverage.
- [ ] Add async background workers for long-running discovery tasks.

### Code quality improvements completed (19-Mar-2026)

- [x] Fix deprecated `datetime.utcnow()` → `datetime.now(timezone.utc)` across all models.
- [x] Fix embedding dimension mismatch (384 vs 768 zero-padding) — schema and model now both use 384.
- [x] Fix database session management — proper context manager with guaranteed close and connection pooling.
- [x] Fix hard-coded embedding model name — now uses `settings.EMBEDDING_MODEL`.
- [x] Fix stale matches — recomputes when professors are updated after last match calculation.
- [x] Standardize SQLAlchemy query style (modern `select()` throughout).
- [x] Add structured logging to previously silent exception handlers.
- [x] Add comprehensive test suite (100+ tests): matching, validation, email, embedding, discovery.

## Definition of done for production-ready MVP

- Authenticated multi-user access with strict data isolation.
- Evidence-backed discovery with automated tests and measurable quality checks.
- Async job workers for discovery/refresh to keep API responsive.
- Reproducible containerized deployment and automated CI checks.
