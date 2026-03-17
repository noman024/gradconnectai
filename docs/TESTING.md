# GradConnectAI — Testing Guide

## Prerequisites

- Backend running: `cd backend && uvicorn app.main:app --reload --port 8009`
- Frontend running: `cd frontend && npm run dev`
- vLLM + Qwen3.5 (optional): `./serve_vllm_qwen.sh` for LLM-powered features
- Database: PostgreSQL with schema applied (`python run_schema.py`)

## Quick smoke test

```bash
# 1. Health
curl -s http://127.0.0.1:8009/api/v1/health | jq .

# 2. Readiness (DB)
curl -s http://127.0.0.1:8009/api/v1/health/ready | jq .

# 3. Create student
STUDENT=$(curl -s -X POST http://127.0.0.1:8009/api/v1/students \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","cv_text":"ML and NLP research","preferences":{"fields":["ML","NLP"]}}')
echo $STUDENT | jq .
export STUDENT_ID=$(echo $STUDENT | jq -r .student_id)

# 4. Discovery (ingest professors)
curl -s -X POST http://127.0.0.1:8009/api/v1/discovery/run \
  -H "Content-Type: application/json" \
  -d '{"seed_urls":["https://aimsl.uiu.ac.bd/"],"university_name":"UIU"}' | jq .

# 5. Matches
curl -s "http://127.0.0.1:8009/api/v1/matches?student_id=$STUDENT_ID" | jq .

# 6. Email draft (use a professor_id from matches)
PROF_ID=$(curl -s "http://127.0.0.1:8009/api/v1/matches?student_id=$STUDENT_ID" | jq -r '.matches[0].professor_id')
curl -s -X POST http://127.0.0.1:8009/api/v1/email-drafts/generate \
  -H "Content-Type: application/json" \
  -d "{\"student_id\":\"$STUDENT_ID\",\"professor_id\":\"$PROF_ID\"}" | jq .
```

## Frontend E2E flow

1. **Home** → `http://localhost:3000` — hero, nav links
2. **Profile** → Upload PDF or paste CV, add fields, submit
3. **Matches** → See ranked professors with names and lab focus
4. **Email** → Generate draft, copy to clipboard

## Accuracy checks

- **Topic extraction:** CV with "machine learning, NLP" should yield topics like `["machine learning","NLP"]`, not names or job titles.
- **Email draft:** Should reference professor's lab focus and student's research topics; no hallucinated names in the body.
- **Matches:** `professor_name`, `university`, `lab_focus` populated when professors exist.

## Rate limits

- Default: 60 requests/minute per IP
- Student create: 30/minute
- PDF upload: 10/minute
- Exceeding returns `429 Too Many Requests`

## Admin (development only)

```bash
curl -s http://127.0.0.1:8009/api/v1/admin/stats | jq .
curl -s http://127.0.0.1:8009/api/v1/admin/professors | jq .
```

In production (`ENVIRONMENT=production`), these return `403`.
