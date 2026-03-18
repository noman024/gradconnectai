# GradConnectAI

- **Author:** MD Mutasim Billah Noman
- **Last Updated:** 18-Mar-2026

AI-driven supervisor discovery and matching for Master's, PhD, and Postdoc students. Discovers potential supervisors from public academic sources, matches them to student profiles via semantic similarity and opportunity signals, and generates personalized outreach email drafts.

## Architecture

- **Dashboard (Next.js)** — Student interface: profile, matches, email review.
- **API (FastAPI)** — REST gateway and service layer.
- **Services:** Portfolio Analyzer, Discovery Engine, Opportunity Detection, Matching Engine, Email Generator.
- **Data:** PostgreSQL (Supabase) with pgvector for embeddings; no Chroma in initial MVP.

## Repository layout

```
GradConnectAI/
├── backend/          # FastAPI app and Python services
│   ├── app/
│   │   ├── api/      # Routes and request handling
│   │   ├── core/     # Config, logging
│   │   ├── db/       # Schema, migrations, session
│   │   ├── services/ # Discovery, portfolio, matching, email
│   │   └── main.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/         # Next.js dashboard
│   ├── src/app/
│   └── package.json
└── README.md
```

## Minimum specs (local / single MacBook)

- **RAM:** 8 GB minimum; 16 GB recommended (vLLM + Postgres + crawlers).
- **Python:** 3.11+.
- **Node:** 18+ for Next.js.
- **PostgreSQL:** 15+ with pgvector extension (Supabase supports it).

Production can move to Vercel (frontend) + Railway/Render (backend + worker) + Supabase (DB).

## Documentation

- [Schema and semantics](docs/SCHEMA_AND_SEMANTICS.md): preferences shape, `opportunity_score` definition, confidence for professor updates, min specs.

## Quick start

### Backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env        # edit with your DATABASE_URL, LLM_BASE_URL, and keys (see below)
uvicorn app.main:app --reload --port 8009
```

### Where to get DATABASE_URL and keys


| Variable              | Where to get it                                                                                                                                                                                                                                                                                                                                 |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **DATABASE_URL**      | **Supabase:** Sign up at [supabase.com](https://supabase.com), create a project, then go to **Project Settings → Database**. Copy the **Connection string** (URI). Use **URI** mode and replace the password. For the async driver use: `postgresql+asyncpg://postgres.[ref]:[YOUR-PASSWORD]@aws-0-[region].pooler.supabase.com:6543/postgres`. |
| **SYNC_DATABASE_URL** | Same as above but with the regular `postgresql://` scheme (no `+asyncpg`). Use the same host, user, password, and database.                                                                                                                                                                                                                     |
| **API_SECRET_KEY**    | Generate your own secret (e.g. for signing sessions). Run: `openssl rand -hex 32` and paste the result. Use a different value in production.                                                                                                                                                                                                    |
| **LLM_BASE_URL**      | Base URL of your OpenAI-compatible LLM server (e.g. Ollama with Qwen3.5 instruct: `http://localhost:11435/v1`, or vLLM: `http://localhost:8010/v1`).                                                                                                                                                                                             |
| **LLM_API_KEY**       | API key for that LLM server (use `EMPTY` for a local Ollama/vLLM server without auth).                                                                                                                                                                                                                                                           |
| **LLM_MODEL**         | Model name: `frob/qwen3.5-instruct:9b` for Ollama (recommended), or `Qwen/Qwen3.5-0.8B` for vLLM.                                                                                                                                                                                                                                               |
| **EMBEDDING_MODEL**   | Name of the embedding model used locally for sentence-transformers (used for pgvector alignment).                                                                                                                                                                                                                                               |
| **ENVIRONMENT**       | Use `development` locally and `production` when deployed.                                                                                                                                                                                                                                                                                       |


**Note:** The app now uses **PostgreSQL** (via `SYNC_DATABASE_URL`) for students, professors, matches, email drafts, opportunities, professor snapshots, and audit logs. Running the schema is required before using the app.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

- Dashboard: [http://localhost:3000](http://localhost:3000)  
- API docs: [http://localhost:8009/docs](http://localhost:8009/docs) (when ENVIRONMENT != production)

### LLM server (Ollama + Qwen instruct)

GradConnectAI expects an OpenAI-compatible LLM endpoint for CV topic extraction, professor structuring, and email drafts. In the current setup, this is provided by Ollama running a Qwen 3.5 instruct model.

#### Option A: Ollama (recommended for Mac)

Ollama works reliably on Apple Silicon and Intel Macs. vLLM on CPU often fails with Qwen3.5.

1. **Install and run Ollama**:

```bash
brew install ollama
ollama serve          # or start the Ollama app
```

2. **Pull the model**:

```bash
./serve_ollama_qwen.sh
# or: ollama pull frob/qwen3.5-instruct:9b
```

3. **Configure** (`backend/.env`):

```env
LLM_BASE_URL=http://localhost:11435/v1
LLM_API_KEY=EMPTY
LLM_MODEL=frob/qwen3.5-instruct:9b
```

#### Option B: vLLM (GPU recommended)

vLLM on **CPU-only** (e.g. Mac without GPU) often fails with Qwen3.5 due to a known bug. Use vLLM if you have a CUDA GPU.

1. **Install vLLM**: `pip install vllm`

2. **Start the server**:

```bash
source backend/.venv/bin/activate
./serve_vllm_qwen.sh        # port 8010
```

3. **Configure** (`backend/.env`):

```env
LLM_BASE_URL=http://localhost:8010/v1
LLM_API_KEY=EMPTY
LLM_MODEL=Qwen/Qwen3.5-0.8B
```

#### GPU selection (vLLM and embeddings)

- **vLLM / Qwen3.5 GPU**: choose which GPU(s) to use via `CUDA_VISIBLE_DEVICES` when starting the server, e.g.:

```bash
CUDA_VISIBLE_DEVICES=0 ./serve_vllm_qwen.sh      # use GPU 0
CUDA_VISIBLE_DEVICES=1 ./serve_vllm_qwen.sh      # use GPU 1
CUDA_VISIBLE_DEVICES=0,1 ./serve_vllm_qwen.sh    # use multiple GPUs (with appropriate vLLM flags)
```

- **Embedding model GPU**: the sentence-transformers encoder defaults to GPU if available, otherwise CPU.  
  You can explicitly pin the device in `backend/.env`:

```env
# Embedding model device override: "cuda", "cuda:0", "cuda:1", "mps", or "cpu"
EMBEDDING_DEVICE=cuda:0
```

If `EMBEDDING_DEVICE` is unset, the service auto-detects: prefers CUDA, then MPS, then CPU, and on CUDA it respects `CUDA_VISIBLE_DEVICES` so you can globally control which GPU is visible.

### Database (run the schema)

With `DATABASE_URL` or `SYNC_DATABASE_URL` set in `backend/.env`, from the **backend** directory run:

```bash
cd backend
source .venv/bin/activate   # if using a venv
python run_schema.py
```

This enables the **pgvector** extension (if available) and applies `app/db/schema.sql`.  
**Supabase:** pgvector is already available; use the connection string from Project Settings → Database (URI).  
**Alternative:** In Supabase SQL Editor, run `CREATE EXTENSION IF NOT EXISTS vector;` then paste and run the contents of `backend/app/db/schema.sql`.

**Existing databases:** If you already have tables and need new columns (`lab_focus`, `opportunity_score`, `experience_snippet`), run:

```bash
cd backend && python run_migrate.py
```

(Or with psql: `psql "$SYNC_DATABASE_URL" -f backend/migrate_add_lab_focus.sql`)

### Cleanup (processes and model caches)

- **Stop all GradConnectAI processes** (backend, vLLM, frontend):

```bash
./scripts/cleanup.sh
```

- **Also remove downloaded model weights** (frees several GB; models re-download on next run):

```bash
./scripts/cleanup.sh --weights
```

- **Manual cleanup:**
  - Kill process on port 8009: `lsof -ti :8009 | xargs kill`
  - Hugging Face / vLLM cache: `rm -rf ~/.cache/huggingface`
  - sentence-transformers: `rm -rf ~/.cache/torch/sentence_transformers`
  - Ollama models: `rm -rf ~/.ollama/models` (then `ollama pull qwen3.5:0.8b` to re-download)

### Managing database data

- List rows (e.g. students):

```bash
psql "$SYNC_DATABASE_URL" -c "SELECT id, name, created_at FROM students ORDER BY created_at DESC LIMIT 20;"
```

- Delete a specific student and associated matches:

```bash
psql "$SYNC_DATABASE_URL" -c "DELETE FROM students WHERE id = '<student-uuid>';"`
```

- Clear all professors and matches (for debugging only):

```bash
psql "$SYNC_DATABASE_URL" -c "TRUNCATE TABLE matches, professors RESTART IDENTITY CASCADE;"
```

## Testing

### Backend API

Run these in a separate terminal with the backend server already running (`uvicorn app.main:app --reload --port 8009`).

- **Health (liveness)**

```bash
curl -i http://127.0.0.1:8009/api/v1/health
```

Expected: `200 OK` and `{"status":"ok","environment":"development"}`.

- **Health (readiness — DB + counts)**

```bash
curl -i http://127.0.0.1:8009/api/v1/health/ready
```

Expected: `200 OK` and `{"status":"ready","database":"connected","professors":N,"students":N}`.

- **Admin stats** (development only; 403 in production)

```bash
curl -i http://127.0.0.1:8009/api/v1/admin/stats
```

- **Create student (Portfolio Analyzer)**

```bash
curl -i -X POST http://127.0.0.1:8009/api/v1/students \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Student",
    "cv_text": "My research focuses on machine learning and NLP.",
    "preferences": {
      "countries": ["Germany"],
      "universities": ["TUM"],
      "fields": ["ML", "NLP"]
    }
  }'
```

Expected: `200 OK` and JSON containing `student_id`, `research_topics`, `embedding_model_version`.

Copy the `student_id`:

```bash
export STUDENT_ID="<paste-student-id>"
curl -i http://127.0.0.1:8009/api/v1/students/$STUDENT_ID
```

- **Discovery + professors**

```bash
curl -i -X POST http://127.0.0.1:8009/api/v1/discovery/run \
  -H "Content-Type: application/json" \
  -d '{
    "seed_urls": ["https://aimsl.uiu.ac.bd/"],
    "university_name": "UIU"
  }'

curl -i http://127.0.0.1:8009/api/v1/professors
```

Expected: `{"ingested": N}` and `{ "professors": [...] }`. Professors are deduplicated by name+university. For each ingested professor, a snapshot and a basic `Opportunity` row are also stored.

Pick a professor id when available:

```bash
export PROF_ID="<paste-professor-id>"
curl -i http://127.0.0.1:8009/api/v1/professors/$PROF_ID
```

- **Matching Engine**

```bash
curl -i "http://127.0.0.1:8009/api/v1/matches?student_id=$STUDENT_ID"
```

Expected: `200 OK` and:

```json
{
  "matches": [
    {
      "professor_id": "...",
      "professor_name": "Dr. X",
      "university": "UIU",
      "lab_focus": "...",
      "score": 0.xx,
      "opportunity_score": 0.xx,
      "final_rank": 0.xx
    }
  ]
}
```

If discovery has not ingested any professors yet, an empty `matches` array is expected.

- **Email Generator**

Requires a valid `PROF_ID` from the professors list.

```bash
curl -i -X POST http://127.0.0.1:8009/api/v1/email-drafts/generate \
  -H "Content-Type: application/json" \
  -d "{\"student_id\": \"$STUDENT_ID\", \"professor_id\": \"$PROF_ID\"}"
```

Expected: `200 OK` and JSON with `subject` and `body`. Uses the configured Qwen3.5 *instruct* model via an OpenAI-compatible endpoint (typically Ollama with `frob/qwen3.5-instruct:9b`); otherwise a template fallback is returned. Each successful call also persists an entry in the `email_drafts` table.

- **GDPR: Export + delete**

```bash
curl -i -X POST "http://127.0.0.1:8009/api/v1/gdpr/export-data?user_id=$STUDENT_ID"
curl -i -X DELETE "http://127.0.0.1:8009/api/v1/gdpr/delete-data?user_id=$STUDENT_ID"
```

Expected:

- Export: `200 OK` with student data and `matches` (if any).
- Delete: `200 OK` with `{"message":"User data deleted"}`. A subsequent export for the same id should return `404`. Both export and delete operations are recorded in the `audit_log` table.

### Admin inspection endpoints (development only)

These are available when `ENVIRONMENT=development` and return `403` in production:

- **Recent audit log entries**

```bash
curl -i "http://127.0.0.1:8009/api/v1/admin/audit?limit=50"
```

- **Email drafts for a student**

```bash
curl -i "http://127.0.0.1:8009/api/v1/admin/students/$STUDENT_ID/email-drafts"
```

- **Professor snapshots and opportunities**

```bash
curl -i "http://127.0.0.1:8009/api/v1/admin/professors/$PROF_ID/snapshots"
curl -i "http://127.0.0.1:8009/api/v1/admin/professors/$PROF_ID/opportunities"
```

### Frontend flows

With `npm run dev` running in `frontend` (and backend at 8009):

1. Open `http://localhost:3000` — the GradConnectAI home page loads.
2. Click **“Start with your profile”** → `http://localhost:3000/profile`.
   - Fill in name, upload a PDF CV or paste CV text, add research fields (e.g. `ML, NLP`).
   - Submit; you are redirected to `/matches`.
3. On `/matches`, if no professors exist you see a message to run discovery; otherwise a ranked list with professor names and lab focus.
4. Click a match to go to `/email/[professorId]` — review the draft and use **Copy to clipboard** to paste into your email client.

## Security and compliance

- **Input validation** on all uploads and text inputs (name, CV text, preferences, file type/size).
- **Rate limiting** (SlowAPI): 60/min default, 30/min for student create, 10/min for PDF upload.
- **File size limit:** 5 MB for CV uploads.
- **GDPR:** Export and delete endpoints under `/api/v1/gdpr`.
- **Audit logging** for profile creation and GDPR operations.
- **Admin endpoints** (`/api/v1/admin/*`) disabled in production.
- **robots.txt** respected by the discovery crawler.

## License

Proprietary. All rights reserved.