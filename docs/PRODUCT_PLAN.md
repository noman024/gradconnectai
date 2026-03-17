# GradConnectAI — Final Product Plan

## 1️⃣ Product Concept

**Goal**  
GradConnectAI automatically discovers potential supervisors for Master’s, PhD, and Postdoc students globally, identifies whether they are actively recruiting or potentially suitable, matches them to student profiles, and generates personalized outreach emails for students to review and send.

**Key Differentiators**

- **100% AI-driven discovery** (no static database; web + academic crawling plus LLM structuring).
- **Covers all postgraduate research fields** (discipline‑agnostic by design).
- **Supports active and potential supervisors** via explicit signals and inferred opportunity_score.
- **Generates email drafts, verified by students** (no auto‑send, student stays in control).
- **Fully automated updates with opportunistic refresh** and scheduled recrawls.
- **Uses free, open-source tools only**, optimized for a solo founder on a single MacBook.
- **Scalable, secure, and maintainable** architecture with clear separation of concerns.


## 2️⃣ Core Workflow

1. **Student profile input**
   - Upload CV (PDF) or paste research summary.
   - Provide preferences: research fields, countries, universities.

2. **Portfolio analysis (student side)**
   - Qwen3.5 via vLLM extracts research topics, keywords, and methods into a structured JSON payload.
   - A sentence‑transformers model converts this into a domain embedding for semantic matching.

3. **Discovery Engine (professor side)**
   - Crawl4AI crawls public web sources:
     - University pages and lab pages.
     - Academic profiles / people directories.
     - Optionally: LinkedIn (with strong respect for ToS and rate limits), arXiv, Semantic Scholar and other academic sources where feasible.
   - Converts pages into LLM‑ready Markdown for robust downstream parsing.

4. **Opportunity Detection Engine**
   - Embedded in the professor extraction prompt and/or downstream scoring:
     - Evaluates active recruitment signals, funding/grants, lab growth, explicit “open positions” language.
     - Produces an `opportunity_score` (0–1) and a short textual reason.

5. **Matching Engine**
   - Computes semantic similarity between the student embedding and professor embeddings → `score` (0–1).
   - Combines `score` with `opportunity_score` into `final_rank`:
     - `final_rank = 0.7 * score + 0.3 * opportunity_score` (tunable weights).
   - Returns a ranked list of supervisors for each student.

6. **Email Generator**
   - Uses Qwen3.5 to produce AI‑generated personalized email drafts based on:
     - Student topics and experience.
     - Professor’s `lab_focus` and `research_topics`.
     - University and any salient overlap between the two.
   - Student always reviews and manually sends the email.

7. **Database**
   - PostgreSQL + pgvector stores:
     - Professors and their structured metadata.
     - Opportunities and opportunity_score.
     - Students, preferences, and embeddings.
     - Matches and email drafts.
   - Designed for automated refresh and historical auditing.


## 3️⃣ System Architecture (Modular)

**Student Dashboard (Next.js)**  
↓  
**API Gateway (FastAPI)**  
↓  
**Service Layer**

- Portfolio Analyzer (AI)
- Discovery Engine (Crawler + Scraper + Crawl4AI)
- Opportunity Detection Engine (AI)
- Matching Engine (Vector Semantic Search)
- Email Generator (AI via Qwen3.5)

↓  
**Data Layer**

- PostgreSQL (structured data, including pgvector)
- Vector embeddings stored in pgvector columns (no separate ChromaDB needed for MVP)

**Design Principles**

- **Modular microservice-lite architecture** (logical services inside a single codebase).
- **Single MacBook deployment first**, but cloud‑ready (Vercel + managed Postgres + containerized vLLM).
- **Secure, maintainable, efficient** with structured logging and clear boundaries.


## 4️⃣ Technology Stack (Free/Open Source)

| Layer        | Tool                                   | Purpose                                                         |
|-------------|----------------------------------------|-----------------------------------------------------------------|
| Frontend    | Next.js + Vercel                      | Student dashboard and interface                                 |
| Backend API | Python + FastAPI                      | REST API endpoints and modular services                         |
| Database    | PostgreSQL (Supabase free tier)       | Structured storage of professors, students, opportunities       |
| Vector DB   | pgvector (PostgreSQL extension)       | Embeddings & similarity search inside Postgres                  |
| AI Models   | Qwen/Qwen3.5 via vLLM                 | Research topic extraction, professor structuring, email drafts  |
| Embeddings  | sentence-transformers (e.g. MiniLM)   | Semantic embeddings for students and professors                 |
| Crawling    | Crawl4AI + Playwright (+ Scrapy/BS4)  | Dynamic discovery of professors and opportunities               |


## 5️⃣ Key System Modules

### Portfolio Analyzer

- Extracts student research topics, methods, and fields using Qwen3.5 with a strict JSON schema (`{"topics":[...]}`).
- Produces a single embedding per student for semantic matching.

### Discovery Engine

- Detects both active recruitment signals and potential supervisors.
- Sources include (prioritized order):
  - Official university faculty and lab pages.
  - Lab “People” pages and group profiles.
  - Academic sources (arXiv, Semantic Scholar) where supervisors are identifiable.
  - LinkedIn and similar platforms **only when legally and ethically acceptable**, with careful handling of robots.txt, rate limits, and ToS.
- Uses Crawl4AI to convert pages into Markdown and Qwen3.5 to extract structured supervisors:
  - `name`, `email`, `lab_focus`, `research_topics`, `opportunity_score`.
- Supports **opportunistic refresh** using `last_checked`, `active_flag`, and `sources` metadata.

### Opportunity Detection Engine

- Evaluates signals such as:
  - Funding, grants, and project announcements.
  - Phrases like “hiring PhD students”, “open positions”, “scholarship available”.
  - Lab growth (new students, recent posts).
- Computes `opportunity_score` (0–1) and a short reason, used in matching and UI.

### Matching Engine

- Computes semantic similarity between student and professor embeddings → `score` (0–1).
- Weighted ranking:
  - `final_rank = score * 0.7 + opportunity_score * 0.3` (configurable weights).
- Returns a ranked list of supervisors with interpretable scores.

### Email Generator

- Uses Qwen3.5 (via vLLM) to generate AI‑personalized email drafts.
- Inputs include:
  - Student topics and key experience.
  - Professor `lab_focus`, `research_topics`, and university.
  - Optionally, salient overlaps (shared domains, methods, or application areas).
- Student reviews and sends manually; no auto‑sending.


## 6️⃣ Database Schema (Conceptual)

**Professors**

| Column         | Type   | Notes                              |
|----------------|--------|------------------------------------|
| id             | UUID   | PK                                 |
| name           | Text   | Full name                          |
| university     | Text   | Current affiliation                |
| email          | Text   | Contact                            |
| research_topics| JSON   | List of topics                     |
| lab_url        | Text   | Website                            |
| lab_focus      | Text   | Short summary of research focus    |
| embedding      | Vector | Semantic representation            |
| last_checked   | Timestamp | Last verification               |
| active_flag    | Boolean| Recently verified?                 |
| sources        | JSON   | URLs / sources of origin           |
| opportunity_score | Float | Likelihood accepting students    |

**Opportunities**

| Column       | Type   | Notes                               |
|--------------|--------|-------------------------------------|
| id           | UUID   | PK                                  |
| professor_id | UUID   | FK to Professors                    |
| type         | Enum   | Master / PhD / Postdoc              |
| funding      | Text   | Fully funded / Partial / Unknown    |
| deadline     | Date   | Application deadline                |
| source       | Text   | URL of discovery                    |

**Students**

| Column         | Type   | Notes                                |
|----------------|--------|--------------------------------------|
| id             | UUID   | PK                                   |
| name           | Text   | Full name                            |
| research_topics| JSON   | Extracted topics                     |
| cv_file        | Text   | File name or URL                     |
| embedding      | Vector | Student embedding                    |
| preferences    | JSON   | Countries / universities / fields    |

**Matches**

| Column          | Type   | Notes                                         |
|-----------------|--------|-----------------------------------------------|
| student_id      | UUID   | FK to Students (part of PK)                   |
| professor_id    | UUID   | FK to Professors (part of PK)                 |
| score           | Float  | Semantic similarity (0–1)                     |
| opportunity_score | Float| Likelihood professor is accepting (0–1)       |
| final_rank      | Float  | Weighted combination of score + opportunity   |

Other tables include **email_drafts**, **professor_snapshots**, and **audit_log** as defined in the SQL schema.


## 7️⃣ Updating Professor Info

- **Opportunistic AI discovery** automatically updates professor profiles when new information is detected.
- **Scheduled refresh**: each professor is re‑checked every X weeks (configurable).
- **High‑confidence updates only**: changes applied when LLM‑based or rule‑based confidence exceeds a threshold (e.g. >90%).
- **Auditability**: previous values are preserved in `professor_snapshots` for debugging and explanations.


## 8️⃣ Development Roadmap

| Phase | Goal                                      | Duration |
|-------|-------------------------------------------|----------|
| 1     | Discovery Engine MVP                      | 3 weeks  |
| 2     | Portfolio Analyzer                        | 1 week   |
| 3     | Matching Engine                           | 2 weeks  |
| 4     | Dashboard (Next.js)                       | 2 weeks  |
| 5     | Email Generator                           | 1 week   |

**Total MVP**: Fully automated discovery + matching + email drafts ≈ **9 weeks** (including integration and polish).


## 9️⃣ Security & Best Practices

- **Crawling and sources**
  - Respect `robots.txt` and rate limits.
  - Prefer public, academic and institutional sources.
  - Treat LinkedIn and similar platforms conservatively, respecting ToS and legal constraints.

- **Input validation & sanitization**
  - Validate all CV uploads (type, size, content) and text inputs.
  - Use strict JSON schemas for LLM outputs.

- **Data protection**
  - Encrypt sensitive data at rest (via Supabase/PG configs).
  - Avoid logging PII.
  - Clear retention policies for CVs, matches, and email drafts.

- **Logging & audit trails**
  - Structured logs with `request_id` for tracing.
  - Audit log for key actions (profile creation, GDPR operations).

- **Rate limiting**
  - API rate limiting per user/IP.
  - Discovery engine rate limiting per domain and globally.


## 🔟 Marketing Strategy

**Target audience**

- Final-year undergraduates.
- Master’s students.
- PhD applicants.
- Research assistants and early‑career researchers.

**Channels**

- **Reddit**: `r/PhD`, `r/GradSchool`, `r/gradadmissions` for early adopters.
- **LinkedIn**: research and graduate study groups; posts targeting supervisors and students.
- **YouTube & blogs**: content like “How to find funded PhD/Master’s positions” powered by GradConnectAI.

**Viral feature**

- Weekly or periodic **email alerts of new opportunities**, personalized by field and region (premium feature).


## 1️⃣1️⃣ Monetization (Freemium)

| Plan    | Features                                                   | Price     |
|---------|------------------------------------------------------------|-----------|
| Free    | 5 matches/month, basic opportunity view                    | $0        |
| Premium | Unlimited matches, AI email generator, opportunity alerts  | $19/month |


## 1️⃣2️⃣ Key Design Decisions

- **Scope**: All postgraduate research (Master’s, PhD, Postdoc).
- **Email**: Drafts only; student reviews and sends manually.
- **Discovery**: 100% AI‑powered from day one (Crawl4AI + Qwen3.5).
- **Architecture**: Modular, scalable, secure; microservice‑lite within a single repo.
- **Tools**: Free, open-source, optimized for a solo founder on a single MacBook, with a clear path to cloud deployment.


## ✅ Why GradConnectAI Will Work

- Solves a highly painful problem: students currently spend months manually hunting for supervisors and funded positions.
- Combines AI discovery, semantic matching, and outreach automation with transparent drafts.
- Modular & scalable architecture enables global reach and easy feature evolution.
- Freemium + viral growth (content + alerts) gives strong potential for sustainable revenue.


