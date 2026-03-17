# GradConnectAI

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

- **RAM:** 8 GB minimum; 16 GB recommended (Ollama + Postgres + crawlers).
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
python3 -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env        # edit with your DATABASE_URL and keys (see below)
uvicorn app.main:app --reload --port 8000
```

### Where to get DATABASE_URL and keys


| Variable              | Where to get it                                                                                                                                                                                                                                                                                                                                 |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **DATABASE_URL**      | **Supabase:** Sign up at [supabase.com](https://supabase.com), create a project, then go to **Project Settings → Database**. Copy the **Connection string** (URI). Use **URI** mode and replace the password. For the async driver use: `postgresql+asyncpg://postgres.[ref]:[YOUR-PASSWORD]@aws-0-[region].pooler.supabase.com:6543/postgres`. |
| **SYNC_DATABASE_URL** | Same as above but with the regular `postgresql://` scheme (no `+asyncpg`). Use the same host, user, password, and database.                                                                                                                                                                                                                     |
| **API_SECRET_KEY**    | Generate your own secret (e.g. for signing sessions). Run: `openssl rand -hex 32` and paste the result. Use a different value in production.                                                                                                                                                                                                    |
| **OLLAMA_BASE_URL**   | Leave as `http://localhost:11434` if you run [Ollama](https://ollama.com) locally. For a remote LLM, set the base URL of that service.                                                                                                                                                                                                          |
| **EMBEDDING_MODEL**   | Leave as `nomic-embed-text` for Ollama, or the model name your embedding API expects.                                                                                                                                                                                                                                                           |
| **ENVIRONMENT**       | Use `development` locally and `production` when deployed.                                                                                                                                                                                                                                                                                       |


**Note:** The app works without a database for MVP: it uses an in-memory store. Set `DATABASE_URL` (and run the schema) when you want to persist professors, students, and matches in Postgres.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

- Dashboard: [http://localhost:3000](http://localhost:3000)  
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs) (when ENVIRONMENT != production)

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

## Testing

### Backend API

Run these in a separate terminal with the backend server already running.

- **Health**

```bash
curl -i http://127.0.0.1:8000/api/v1/health
```

Expected: `200 OK` and `{"status":"ok"}`.

- **Create student (Portfolio Analyzer)**

```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/students \
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
curl -i http://127.0.0.1:8000/api/v1/students/$STUDENT_ID
```

- **Discovery + professors (optional for now)**

```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/discovery/run \
  -H "Content-Type: application/json" \
  -d '{
    "seed_urls": ["https://<some-public-lab-or-faculty-page>"],
    "university_name": "Example University"
  }'

curl -i http://127.0.0.1:8000/api/v1/professors
```

Expected: `{"ingested": N}` and `{ "professors": [...] }` (may be empty).

Pick a professor id when available:

```bash
export PROF_ID="<paste-professor-id>"
curl -i http://127.0.0.1:8000/api/v1/professors/$PROF_ID
```

- **Matching Engine**

```bash
curl -i "http://127.0.0.1:8000/api/v1/matches?student_id=$STUDENT_ID"
```

Expected: `200 OK` and:

```json
{ "matches": [ { "professor_id": "...", "score": 0.xx, "opportunity_score": 0.xx, "final_rank": 0.xx }, ... ] }
```

If discovery has not ingested any professors yet, an empty `matches` array is expected.

- **Email Generator**

Requires a valid `PROF_ID` from the professors list.

```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/email-drafts/generate \
  -H "Content-Type: application/json" \
  -d "{\"student_id\": \"$STUDENT_ID\", \"professor_id\": \"$PROF_ID\"}"
```

Expected: `200 OK` and JSON with `subject` and `body`. When Ollama is not running, a simple fallback email body is returned.

- **GDPR: Export + delete**

```bash
curl -i -X POST "http://127.0.0.1:8000/api/v1/gdpr/export-data" -d "user_id=$STUDENT_ID"
curl -i -X DELETE "http://127.0.0.1:8000/api/v1/gdpr/delete-data" -d "user_id=$STUDENT_ID"
```

Expected:

- Export: `200 OK` with student data and `matches` (if any).
- Delete: `200 OK` with `{"message":"User data deleted"}`. A subsequent export for the same id should return `404`.

### Frontend flows

With `npm run dev` running in `frontend`:

1. Open `http://localhost:3000` — the GradConnectAI home page should load without 404.
2. Click **“Create profile”** → `http://localhost:3000/profile`.
   - Fill in name, paste some CV text, add a few fields (e.g. `ML, NLP`).
   - Submit; you should be redirected to `/matches`.
3. On `/matches`, if no professors exist yet you will see a message telling you to add data; once discovery has ingested professors, you should see a ranked list.
4. Click a match entry to go to `/email/[professorId]` and see an email draft you can copy and send manually.

## Security and compliance

- **Input validation** on all uploads and text inputs.
- **Rate limiting** on API and crawler (per-domain and global).
- **GDPR:** Retention policies for CVs, matches, and email drafts; export and delete endpoints under `/api/v1/gdpr`.
- **Audit logging** for security and product analytics.
- **robots.txt** respected by the discovery crawler from day one.

## License

Proprietary. All rights reserved.