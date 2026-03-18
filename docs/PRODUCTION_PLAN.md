# GradConnectAI — Productionization Plan (Tracked Tasks)

This doc tracks the remaining work to productionize GradConnectAI end-to-end, aligned with `docs/PRODUCT_PLAN.md` and the current repo state.

## Non‑negotiables (per product decisions)

- **Discovery**: build our own SERP-like discovery using **browser automation** (Playwright) + crawling.
- **Search engine (v1)**: **Google** first.
- **Social discovery (v1)**: include **LinkedIn post search** and prioritize recency (latest posts signal authentic opportunities).
- **Evidence policy**: **do not insert/update** a professor unless **name + (email OR profile URL)** is explicitly found in page text/DOM and stored as evidence.
  - **Email required when available**: if an email exists on the page, extraction must capture it and gate on it (do not accept “profile URL only” if an email is present but not captured).
- **Accounts**: ship **full auth now** (real users, isolation, sessions).
- **Infrastructure**: **containerized** deployment (Docker) for backend + workers + frontend + DB.
- **LLM deployment**: containerize **Ollama + vLLM** (configurable routing).
- **Priority**: treat breadth + correctness + cost/speed as **all required** (use phased rollout but no “ignore X”).

---

## Phase 0 — Project hygiene (1–2 days)

- [ ] **Create env templates**: add `.env.example` for frontend (API base, auth config).
- [ ] **Make ports consistent**: standardize backend port and frontend `NEXT_PUBLIC_API_BASE` defaults.
- [ ] **Add a Makefile**: common commands (`dev`, `lint`, `test`, `docker-up`, `migrate`).
- [ ] **Add CI skeleton**: basic lint + unit tests + type checks (GitHub Actions).

**Exit criteria**
- `docker compose up` brings up the full stack locally with one command.

---

## Phase 1 — Evidence-gated discovery (core correctness) (1–2 weeks)

### 1.1 Evidence model + DB changes

- [x] **Add evidence tables** (new schema):
  - `source_documents`: url, fetched_at, content_hash, raw_text/markdown pointer, http status, robots allowed
  - `extraction_runs`: model/version, prompt_version, started_at, finished_at, success, error
  - `professor_evidence`: professor_id, url, evidence_type (email/name/profile_url), selector/snippet, confidence
- [x] **Store model versions** for each extraction (LLM + embeddings).
- [ ] **Retention rules** for source documents and evidence (configurable).

- [x] **Make schema re-runnable**: `opportunity_type` enum creation is now idempotent so `run_schema.py` can be executed repeatedly.

- [x] **LLM context sizing is configurable**: added `LLM_MAX_INPUT_CHARS` and per-task output token caps so Qwen long-context can be used safely.

### 1.2 Strict extraction gates (no hallucinations)

- [x] **Name gate**: extracted `name` must appear in the source (normalized match).
- [x] **Email OR profile URL gate**:
  - If email present: must appear in the source (regex match + exact span capture).
  - If profile URL present: must be a real link in the DOM (anchor href captured).
- [x] **Email required when available**:
  - If the source page contains an email address, the accepted extraction must include it as evidence.
  - Only allow “profile URL only” when no email exists on the page (or page is email-obfuscated and we can’t legally/robustly recover it).
- [~] **Evidence persistence**:
  - Implemented: `professor_evidence` rows persist name/email/profile_url evidence values per professor.
  - TODO: persist **DOM selectors/snippets** (currently `selector`/`snippet` are stored but not populated consistently).
- [x] **Reject UI labels / roles**: block common non-person strings (contact, apply, positions, etc.) at the extractor level.
- [ ] **Unit tests** for gates using saved HTML fixtures.

### 1.3 Discovery pipeline refactor (LLM + evidence)

- [x] **Split discovery into steps**:
  - Fetch → normalize → extract candidates → validate with evidence → upsert
- [ ] **Add “dry run” mode**: return extracted candidates + evidence without DB writes.
- [x] **Add structured logs** per URL: fetch status, extracted candidates count, accepted count, rejection reasons.

**Exit criteria**
- Running discovery on job boards does **not** pollute `professors`.
- Every inserted professor has stored evidence for name + email/profile URL.

**Notes**
- Crawl4AI requires Playwright Chromium installed (`playwright install chromium`). Without it, discovery should return `ingested: 0` and log a Crawl4AI startup error (no 500s).
- Current discovery is **Qwen-only** (heuristic fallbacks removed); correctness is enforced via hard evidence gates.

---

## Phase 2 — “Own SERP” via browser automation (Playwright) (2–4 weeks)

### 2.1 Query planning from student profile

- [ ] **Query builder (LLM-assisted)**:
  - Inputs: student topics, preferences (countries/unis/fields), target degree
  - Outputs: list of search intents + query strings + constraints
- [ ] **Guardrails**: cap query count, dedupe, avoid unsafe queries, add “site:” targeting when appropriate.

### 2.2 Browser-based search runner

- [ ] **Search runner with Playwright**:
  - Run queries on **Google** (v1), engines configurable later
  - Extract top‑K results per query (URL + title + snippet + rank)
  - Respect rate limits + randomized waits + per-engine quotas
- [ ] **LinkedIn post discovery (Playwright)**:
  - **Support login automation** (session/cookie persistence); run LinkedIn-native searches for:
    - **posts** (primary for fresh opportunities)
    - **people profiles** (authors and potential supervisors)
    - **company/university pages** (labs, departments, centers)
  - Extract top‑K post URLs with metadata: author name, author profile URL, post timestamp (when visible), snippet.
  - **Recency-first**: prioritize newer posts during URL selection and in downstream opportunity scoring.
  - Cache results per query+day to reduce repeated browsing and rate-limit impact.
- [ ] **LinkedIn session management**:
  - Persist authenticated storage state (Playwright) in a secure location (encrypted at rest in production).
  - Handle MFA/2FA: manual bootstrap flow (operator logs in once, we reuse storage state) + periodic re-auth.
  - Add safety fallbacks: if LinkedIn blocks/invalidates the session, fall back to Google/Bing `site:linkedin.com/*` queries.
- [ ] **Anti-breakage**:
  - DOM selector versioning
  - Fallback extraction strategies for results (multiple selectors)
- [ ] **Cache**: store SERP results by query+day to reduce cost and avoid repeated browsing.

### 2.3 Candidate URL prioritization

- [ ] **URL scoring**:
  - Boost university/lab pages, faculty directories, personal academic pages
  - Boost LinkedIn posts that contain explicit hiring/funding language and have recent timestamps
  - Downrank generic job boards unless they contain real professor contact/profile links
- [ ] **Top‑K crawl plan** per student session.

**Exit criteria**
- Given `student_id`, system can autonomously discover a high-quality set of URLs and ingest evidence-backed professors.

---

## Phase 3 — Accounts & auth (2–3 weeks)

- [ ] **User model**: users table + link `students` to `user_id` (one-to-many or one-to-one).
- [ ] **Auth (v1)**: **Google OAuth** + sessions/JWT.
- [ ] **Authorization**: enforce per-user access on all endpoints (students, matches, drafts).
- [ ] **Rate limiting per user** (not just per IP).
- [ ] **GDPR**: export/delete should operate by authenticated user and include evidence artifacts.
- [ ] **Frontend auth flows**: signup/login/logout, protected pages, session persistence.

**Exit criteria**
- No endpoint allows cross-user access via guessing IDs.

---

## Phase 4 — Workers, scheduling, and scale (2–4 weeks)

- [ ] **Job queue** (containerized worker):
  - discovery fetch jobs
  - SERP jobs
  - extraction jobs
  - refresh jobs
- [ ] **Retry/backoff** for transient failures.
- [ ] **Scheduled refresh**:
  - refresh professors by `last_checked` age
  - refresh high-interest professors (based on user interactions)
- [ ] **Vector search in DB**:
  - move match computation to pgvector queries for scale
  - keep current python fallback only for dev

**Exit criteria**
- Discovery runs asynchronously with progress; API stays responsive.

---

## Phase 5 — Opportunity engine (structured opportunities) (2–3 weeks)

- [ ] **Opportunity extraction**:
  - identify explicit openings, funding, deadlines, position type
  - store as `opportunities` rows with evidence URLs/snippets
- [ ] **Opportunity scoring**:
  - calibrate `opportunity_score` using explicit signals + recency
- [ ] **UI**:
  - show opportunity details and evidence links/snippets

**Exit criteria**
- Opportunities are inspectable and evidence-backed, not just a single float.

---

## Phase 6 — Production infra (containerized) (1–2 weeks)

- [ ] **Dockerfiles**:
  - backend API
  - worker
  - frontend
- [ ] **Docker Compose**:
  - Postgres + pgvector
  - API
  - worker
  - frontend
  - **Ollama container**
  - **vLLM container**
- [ ] **Migrations**:
  - switch from “run schema.sql” to a migration tool (Alembic) for production evolution
- [ ] **Observability**:
  - structured logs + request_id everywhere
  - Sentry (backend + frontend)
  - metrics (basic Prometheus) if needed
- [ ] **Secrets**:
  - production secrets injected via orchestrator, not committed

**Exit criteria**
- A clean deployment path exists for staging + production with repeatable builds.

---

## Phase 7 — QA, monitoring, and abuse prevention (ongoing)

- [ ] **E2E tests**: critical flows (signup → profile → discovery → matches → email draft).
- [ ] **Load test**: discovery concurrency, worker throughput, DB performance.
- [ ] **Abuse prevention**:
  - per-user quotas for discovery/search
  - domain allow/deny lists
  - crawl budget management
- [ ] **Cost controls**:
  - caching everywhere (SERP + fetch + extraction)
  - batch LLM calls
  - model routing (small model for classification, larger only when needed)

---

## Open questions (need your feedback)

Resolved:

- **Search engines first**: Google.
- **Google automation fallback**: implement fallback engine(s) (start with **Bing**, then DDG if needed).
- **LinkedIn**: include LinkedIn-native post search + profile discovery; prioritize recent posts for authenticity.
- **Evidence minimum**: email required when available.
- **Auth UX**: Google OAuth.
- **OAuth providers**: Google-only.
- **LLM deployment default**: containerized Ollama + vLLM.
- **LLM routing**: env-configurable “all Ollama” vs “all vLLM”.
- **Email obfuscation**: implement an industry-standard, robust email extraction pipeline with evidence capture:
  - **Primary**: `mailto:` links from rendered DOM (`<a href="mailto:...">`), store href + selector.
  - **Secondary**: plain emails found in rendered visible text (regex), store the surrounding snippet + selector/DOM path.
  - **Obfuscation decode** (allowed): common text patterns such as:
    - `name [at] domain [dot] edu`, `name(at)domain(dot)edu`, `name at domain dot edu`
    - HTML entities / spacing variants (e.g. `name&#64;domain.edu`, `name @ domain . edu`)
    - “anti-spam” tokens like `REMOVE_THIS`, `(remove)` where the final result is unambiguous
    - Store both **raw matched text** and **decoded email** as evidence.
  - **JS-rendered emails**: allowed via Playwright rendering (we still require evidence in the DOM/text after render).

Remaining:

None (decisions captured above). If new constraints appear (e.g. Google blocks), we revisit engine ordering and quotas.

---

## Current status summary (synced with repo)

- **Implemented**
  - Evidence tables + ORM models + store helpers (`source_documents`, `extraction_runs`, `professor_evidence`)
  - Qwen extraction includes `profile_url` and enforces evidence gates (name-in-text; email required when available; else profile_url)
  - Crawl4AI/Playwright missing-binary failure is handled gracefully (no 500s)
  - Context sizing is configurable via env (`LLM_MAX_INPUT_CHARS`, `LLM_MAX_OUTPUT_TOKENS_*`)

- **Not implemented yet**
  - Dry-run discovery mode
  - Unit tests + fixtures for evidence gates
  - Retention jobs for evidence/source docs
  - SERP (Google/Bing) + LinkedIn search automation
  - Google OAuth + user model + authorization
  - Containerization (Dockerfiles + Compose) and migrations (Alembic)

