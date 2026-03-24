# GradConnectAI

- **Author:** MD Mutasim Billah Noman
- **Last Updated:** 20-Mar-2026

AI-driven supervisor discovery and matching for Master's, PhD, and Postdoc students.

## Architecture

- **Frontend:** Next.js dashboard (`/`, `/profile`, `/matches`, `/email/[professorId]`)
- **Backend:** FastAPI API + modular services (portfolio, discovery, matching, email generation)
- **Data:** PostgreSQL + pgvector
- **LLM:** OpenAI-compatible endpoint (Ollama or vLLM)

## System Pipeline

- Student uploads CV (PDF/text) -> backend extracts topics/skills and builds profile embedding.
- System constructs discovery intents/keywords -> searches and selects high-value source URLs/posts using Google/LinkedIn and integrated harvesters.
- Seed URLs are prioritized by quality/relevance/freshness -> Crawl4AI fetches and normalizes pages -> Qwen extracts professor/opportunity signals with evidence gating.
- Matching ranks supervisors by semantic fit + opportunity score, with opportunity explanations -> user gets ranked results and personalized email drafts.

## Repository Layout

```text
GradConnectAI/
├── config/              # Single source env file: app.env
├── backend/             # FastAPI app and services
├── frontend/            # Next.js dashboard
├── docs/PRODUCT_PLAN.md # Product roadmap and implementation status
└── README.md            # Setup + run + test guide
```

## Product Plan

- [docs/PRODUCT_PLAN.md](docs/PRODUCT_PLAN.md)

## Prerequisites

- Python 3.11+
- Node 18+
- PostgreSQL 15+ with `pgvector`
- Optional local LLM backend: Ollama or vLLM

## Step-by-step Setup (Easy Run)

### 1) Configure environment

Base runtime configuration lives in `config/app.env`.

```bash
cp config/app.env.example config/app.env
```

Edit `config/app.env` and set at least:

- `SYNC_DATABASE_URL`
- `LLM_BASE_URL`
- `LLM_MODEL`

For local machine secrets, prefer an untracked override file:

```bash
cp config/app.local.env.example config/app.local.env
```

Values are resolved with this precedence:
- shell environment variables
- `config/app.local.env`
- `config/app.env`

### 2) Setup and run backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

Apply DB schema:

```bash
python run_schema.py
```

If upgrading an existing DB:

```bash
python run_migrate.py
```

Start backend:

```bash
uvicorn app.main:app --reload --port 8009
```

### 3) Setup and run frontend

```bash
cd frontend
npm install
npm run dev
```

### 4) Open app

- Dashboard: [http://localhost:3000](http://localhost:3000)
- API docs: [http://localhost:8009/docs](http://localhost:8009/docs) (when `ENVIRONMENT != production`)

## Active Environment Variables

| Variable | Purpose |
| --- | --- |
| `NEXT_PUBLIC_API_BASE` | Frontend API base URL |
| `ENVIRONMENT` | `development` or `production` |
| `CORS_ORIGINS` | Comma-separated frontend origins |
| `LOG_LEVEL` | Backend log level |
| `API_RATE_LIMIT_PER_MINUTE` | Default API per-IP limit |
| `API_RATE_LIMIT_UPLOAD_PER_MINUTE` | Upload endpoint per-IP limit |
| `MAX_CV_FILE_SIZE_MB` | Max CV upload size |
| `SYNC_DATABASE_URL` | PostgreSQL connection URL used by backend |
| `OLLAMA_BASE_URL` | Ollama embeddings endpoint base |
| `EMBEDDING_MODEL` | Sentence embedding model |
| `EMBEDDING_DEVICE` | Optional device override (`cuda:0`, `mps`, `cpu`) |
| `LLM_BASE_URL` | OpenAI-compatible LLM base URL |
| `LLM_API_KEY` | LLM API key (`EMPTY` for local runtime) |
| `LLM_MODEL` | LLM model identifier |
| `LLM_MAX_INPUT_CHARS` | Max chars sent to LLM |
| `LLM_MAX_OUTPUT_TOKENS_TOPICS` | Output cap for topic extraction |
| `LLM_MAX_OUTPUT_TOKENS_PROFESSORS` | Output cap for professor extraction |
| `LLM_MAX_OUTPUT_TOKENS_EMAIL` | Output cap for email generation |
| `CRAWL4AI_HEADLESS` | Crawl4AI browser mode (`1` headless, `0` visible) |
| `CRAWL4AI_FORCE_HEADLESS_IF_NO_DISPLAY` | Auto-force headless if no `DISPLAY`/`WAYLAND_DISPLAY` is available |
| `GOOGLE_BROWSER_HEADLESS` | Browser ingestion headless mode |
| `GOOGLE_BROWSER_TIMEOUT_MS` | Browser navigation timeout for Google ingestion |
| `GOOGLE_BROWSER_WAIT_MS` | Post-load wait before parsing search results |
| `LINKEDIN_SESSION_TTL_MINUTES` | LinkedIn discovery session TTL |
| `LINKEDIN_MAX_RESULTS_PER_QUERY` | Max LinkedIn links kept per query |
| `LINKEDIN_LI_AT` | Optional LinkedIn `li_at` cookie for authenticated LinkedIn discovery |
| `LINKEDIN_COOKIE_HEADER` | Optional full LinkedIn `Cookie` header for stronger authenticated discovery |
| `LINKEDIN_BROWSER_HEADLESS` | LinkedIn authenticated browser discovery headless mode |
| `LINKEDIN_BROWSER_TIMEOUT_MS` | Browser navigation timeout for LinkedIn discovery |
| `LINKEDIN_BROWSER_SCROLL_STEPS` | Scroll passes to load more LinkedIn results |
| `LINKEDIN_BROWSER_SCROLL_WAIT_MS` | Wait between scroll passes for dynamic content |
| `SEARCH_PROVIDER_ORDER` | Search provider order (default: `brave,bing,bing_rss,duckduckgo`). Brave is preferred for reliability from VPN/server IPs. |
| `SEARCH_PROXY_URLS` | Optional comma-separated proxies for request rotation |
| `SEARCH_ENABLE_GOOGLE` | Enable/disable Google provider usage (`1`/`0`, default `0`) |
| `SEARCH_GOOGLE_COOLDOWN_SECONDS` | Cooldown after Google 429 before next Google attempt |

## LLM Backend Options (Ollama and vLLM)

The backend is synced for both runtimes through the same env keys:
`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`.

### Option A: Ollama (recommended default)

```bash
brew install ollama
ollama serve
./serve_ollama_qwen.sh
```

Set in `config/app.env`:

```env
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=EMPTY
LLM_MODEL=frob/qwen3.5-instruct:9b
```

### Option B: vLLM (GPU recommended)

```bash
source backend/.venv/bin/activate
./serve_vllm_qwen.sh
```

Set in `config/app.env`:

```env
LLM_BASE_URL=http://localhost:8010/v1
LLM_API_KEY=EMPTY
LLM_MODEL=Qwen/Qwen3.5-0.8B
```

GPU selection examples:

```bash
CUDA_VISIBLE_DEVICES=0 ./serve_vllm_qwen.sh
CUDA_VISIBLE_DEVICES=1 ./serve_vllm_qwen.sh
CUDA_VISIBLE_DEVICES=0,1 ./serve_vllm_qwen.sh
```

Embedding device override:

```env
EMBEDDING_DEVICE=cuda:0
```

## Quick API Test

With backend running:

```bash
# Health
curl -s http://127.0.0.1:8009/api/v1/health | jq .
curl -s http://127.0.0.1:8009/api/v1/health/ready | jq .

# Create student
STUDENT=$(curl -s -X POST http://127.0.0.1:8009/api/v1/students \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","cv_text":"ML and NLP research","preferences":{"fields":["ML","NLP"]}}')
echo "$STUDENT" | jq .
export STUDENT_ID=$(echo "$STUDENT" | jq -r .student_id)

# Discovery (known working fixture)
curl -s -X POST http://127.0.0.1:8009/api/v1/discovery/run \
  -H "Content-Type: application/json" \
  -d '{"seed_urls":["https://cse.uiu.ac.bd/faculty/"],"university_name":"UIU"}' | jq .

# Discovery dry-run (no DB writes; returns extracted candidates + evidence)
curl -s -X POST http://127.0.0.1:8009/api/v1/discovery/run \
  -H "Content-Type: application/json" \
  -d '{"seed_urls":["https://cse.uiu.ac.bd/faculty/"],"university_name":"UIU","dry_run":true}' | jq .

# Discovery query plan from student profile signal
curl -s -X POST http://127.0.0.1:8009/api/v1/discovery/query-plan \
  -H "Content-Type: application/json" \
  -d '{"research_topics":["machine learning","NLP"],"preferences":{"universities":["UIU"],"countries":["Bangladesh"],"degree_targets":["MS","PhD"]}}' | jq .

# Browser-based Google ingestion MVP (Playwright-backed)
curl -s -X POST http://127.0.0.1:8009/api/v1/discovery/google-search-browser \
  -H "Content-Type: application/json" \
  -d '{"queries":["machine learning professor open position"],"max_links_per_query":10}' | jq .

# Note: browser-use agentic search endpoints can take 2-10 minutes depending on query complexity.
# This is expected behavior for deeper exploratory search.

# LinkedIn discovery MVP (session + recency-weighted ranking)
curl -s -X POST http://127.0.0.1:8009/api/v1/discovery/linkedin-discovery \
  -H "Content-Type: application/json" \
  -d '{"queries":["machine learning professor hiring"],"max_links_per_query":8}' | jq .

# LinkedIn discovery with authenticated cookie (better post coverage)
curl -s -X POST http://127.0.0.1:8009/api/v1/discovery/linkedin-discovery \
  -H "Content-Type: application/json" \
  -d '{"queries":["phd in ai"],"li_at_cookie":"<YOUR_LINKEDIN_LI_AT_COOKIE>","max_links_per_query":8}' | jq .

# Latest LinkedIn posts mode (post-only, recency-first)
curl -s -X POST http://127.0.0.1:8009/api/v1/discovery/linkedin-discovery \
  -H "Content-Type: application/json" \
  -d '{"queries":["phd in ai"],"li_at_cookie":"<YOUR_LINKEDIN_LI_AT_COOKIE>","posts_only":true,"latest_first":true,"max_links_per_query":30}' | jq .

# You can pass full cookie header if li_at alone is not enough
# {"queries":["phd in ai"],"cookie_header":"li_at=...; JSESSIONID=...; liap=true; ...","posts_only":true}

# Default provider order: Brave Search (most reliable from VPN/server IPs),
# then Bing, Bing RSS, DuckDuckGo as fallbacks.
# SEARCH_PROVIDER_ORDER=brave,bing,bing_rss,duckduckgo
# SEARCH_ENABLE_GOOGLE=0

# Integrated automated harvester (query-plan + Google + LinkedIn -> ranked seed URLs)
curl -s -X POST http://127.0.0.1:8009/api/v1/discovery/harvest \
  -H "Content-Type: application/json" \
  -d '{"research_topics":["machine learning","NLP"],"preferences":{"universities":["UIU"],"countries":["Bangladesh"]},"use_browser_google":true,"max_queries_per_source":4,"max_links_per_query":8,"top_k":20}' | jq .

# Verified-only harvest mode (drops noisy/unverified links)
curl -s -X POST http://127.0.0.1:8009/api/v1/discovery/harvest \
  -H "Content-Type: application/json" \
  -d '{"research_topics":["machine learning","NLP"],"preferences":{"universities":["UIU"],"countries":["Bangladesh"],"degree_targets":["MS","PhD"]},"verified_only":true,"use_browser_google":true,"max_queries_per_source":4,"max_links_per_query":8,"top_k":20}' | jq .

# Matches
curl -s "http://127.0.0.1:8009/api/v1/matches?student_id=$STUDENT_ID" | jq .

# Admin evidence cleanup dry-run (development only)
curl -s -X POST http://127.0.0.1:8009/api/v1/admin/cleanup/evidence \
  -H "Content-Type: application/json" \
  -d '{"older_than_days":90,"dry_run":true}' | jq .
```

## Docker Deployment

```bash
# Build and start all services (Postgres + backend + frontend)
docker compose up --build -d

# View logs
docker compose logs -f backend

# Tear down
docker compose down
```

The `docker-compose.yml` includes PostgreSQL with pgvector, the backend API, and the frontend.
Schema is auto-applied on first Postgres startup. Ensure `config/app.env` exists before running.

## Run Tests

```bash
cd backend
source .venv/bin/activate
python -m pytest -v
```

**Test coverage (120 tests):**
- Matching engine (cosine similarity, ranking, cold start)
- Input validation (name, CV text, preferences, UUID)
- Email generation (topic sanitization, fallback, meta-reasoning cleanup)
- Embedding service (dimension, fallback, model loading)
- Evidence gate (acceptance/rejection logic with fixtures)
- Google/LinkedIn/browser search (URL building, scoring, dedup)
- Harvester (merge, filtering, orchestration)
- Query planner (query generation, empty inputs)
- URL prioritizer (ranking heuristics)

## CI

GitHub Actions workflow is available at `.github/workflows/ci.yml` and runs:
- backend `pytest`
- frontend `npm run lint`
- frontend `npm test`
- frontend `npm run build`
- API smoke checks (`/api/v1/health`, `/api/v1/health/ready`)

## Security Notes

- Input validation for file uploads and text fields
- API rate limiting via SlowAPI
- GDPR export/delete endpoints at `/api/v1/gdpr`
- Admin routes disabled in production

## License

Proprietary. All rights reserved.

