# GradConnectAI

- **Author:** MD Mutasim Billah Noman
- **Last Updated:** 18-Mar-2026

AI-driven supervisor discovery and matching for Master's, PhD, and Postdoc students.

## Architecture

- **Frontend:** Next.js dashboard (`/`, `/profile`, `/matches`, `/email/[professorId]`)
- **Backend:** FastAPI API + modular services (portfolio, discovery, matching, email generation)
- **Data:** PostgreSQL + pgvector
- **LLM:** OpenAI-compatible endpoint (Ollama or vLLM)

## System Pipeline

- Student uploads CV (PDF/text) -> backend extracts topics/skills and builds profile embedding.
- System constructs discovery intents/keywords -> searches and selects high-value source URLs/posts (Google/LinkedIn roadmap).
- Seed URLs are prioritized by quality/relevance/freshness -> Crawl4AI fetches and normalizes pages -> Qwen extracts professor/opportunity signals with evidence gating.
- Matching ranks supervisors by semantic fit + opportunity score -> user gets ranked results and personalized email drafts.

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

All runtime configuration is controlled only via `config/app.env`.

```bash
cp config/app.env.example config/app.env
```

Edit `config/app.env` and set at least:

- `SYNC_DATABASE_URL`
- `LLM_BASE_URL`
- `LLM_MODEL`

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
  -d '{"research_topics":["machine learning","NLP"],"preferences":{"universities":["UIU"],"countries":["Bangladesh"]}}' | jq .

# Google ingestion MVP (collect + dedupe + score links)
curl -s -X POST http://127.0.0.1:8009/api/v1/discovery/google-search \
  -H "Content-Type: application/json" \
  -d '{"queries":["machine learning professor open position"],"max_links_per_query":10}' | jq .

# Matches
curl -s "http://127.0.0.1:8009/api/v1/matches?student_id=$STUDENT_ID" | jq .

# Admin evidence cleanup dry-run (development only)
curl -s -X POST http://127.0.0.1:8009/api/v1/admin/cleanup/evidence \
  -H "Content-Type: application/json" \
  -d '{"older_than_days":90,"dry_run":true}' | jq .
```

## Run Tests

```bash
cd backend
source .venv/bin/activate
python -m pytest -q
```

Evidence-gating fixtures and tests live under `backend/tests/fixtures/evidence_gate` and
`backend/tests/test_evidence_gate.py`.

## CI

GitHub Actions workflow is available at `.github/workflows/ci.yml` and runs:
- backend `pytest`
- frontend `npm run lint`
- frontend `npm run build`
- API smoke checks (`/api/v1/health`, `/api/v1/health/ready`)

## Security Notes

- Input validation for file uploads and text fields
- API rate limiting via SlowAPI
- GDPR export/delete endpoints at `/api/v1/gdpr`
- Admin routes disabled in production

## License

Proprietary. All rights reserved.

