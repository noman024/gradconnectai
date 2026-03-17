# Schema and semantics

## Student preferences shape

Used in API and matching. Frontend and backend must stay in sync.

```json
{
  "countries": ["Germany", "UK"],
  "universities": ["TU Munich", "Oxford"],
  "fields": ["Machine Learning", "NLP", "HCI"]
}
```

- **countries**: Preferred countries for study (optional filter in matching).
- **universities**: Preferred institutions (optional boost or filter).
- **fields**: Research areas; used by Portfolio Analyzer and for display.

All arrays are optional; max 50 items per key, each item max 100 characters.

---

## opportunity_score (0–1)

**Definition:** Likelihood that the professor is currently accepting students (Master’s / PhD / Postdoc).

**Intended formula (to be implemented in Opportunity Detection Engine):**  
Weighted combination of:

- Has open position (recent posting or “we are hiring” signal)
- Recent grant/funding (e.g. last 24 months)
- Lab growth (new members, new projects)
- Recent publication with students (co-authorship)

**Current MVP:** Default 0.5 when no signals; can be set from discovery (e.g. “open position” → higher).

**Interpretability:** Prefer showing a short explanation, e.g.  
“Opportunity: High — open PhD position (2024), recent grant (2023).”

---

## Confidence for professor updates

**Definition (plan: “only update if confidence > 90%”):**

- **Confidence** = measure that new data is correct before overwriting existing professor fields.
- **Options for implementation:**
  - **Model score:** e.g. extraction confidence from NER/LLM (0–1).
  - **Source agreement:** e.g. same email on official university page + lab page → high confidence.
  - **Manual rule:** e.g. “email found on official *.edu faculty page” → 0.95.

**Recommendation:** Start with a rule-based confidence: e.g.  
- Official university domain + faculty listing → 0.95  
- Lab page only → 0.7  
- Other → 0.5  
Then only update if `confidence >= 0.9`.

---

## Minimum specs (local / single MacBook)

- **RAM:** 8 GB minimum; 16 GB recommended (Ollama + Postgres + crawlers).
- **Python:** 3.11+.
- **Node:** 18+ for Next.js.
- **PostgreSQL:** 15+ with pgvector extension (Supabase supports it).

Production: Vercel (frontend) + Railway/Render (backend + worker) + Supabase (DB).
