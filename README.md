# ControlPlane.ai

> **Live demo:** [samruddhisadar-gradeops.hf.space](https://samruddhisadar-gradeops.hf.space)
> **GitHub:** [github.com/samsadar236/controlplane-pandas](https://github.com/samsadar236/controlplane-pandas)
> **Team Pandas · Accenture Innovation Challenge 2026 · Round 2**

---

A Responsible AI Checker — a black-box guardrail layer that flags hallucination, privacy leaks, and bias in AI output before it reaches a human.

Built for the Accenture Innovation Challenge Round 2. ControlPlane.ai generalizes the Round 1 project GradeOps (a human-in-the-loop grading pipeline), whose critic-and-grounding mechanism was effectively a narrow responsible-AI checker. Round 2 extracts that engine into a general checker that can wrap any AI output, and keeps the exam-grading pipeline as the worked vertical.

**Stack:** FastAPI · React · LangGraph · HHEM-2.1-Open · SQLite / PostgreSQL

---

## What it does

Enterprises run generative AI across many use cases at once — customer chatbots, internal copilots, decision-support tools — each with a different risk tolerance. ControlPlane.ai sits over that output as a checker and:

- Detects **hallucination** (grounding), **privacy leaks** (PII), and **bias**, using deterministic checks first and an LLM judge only when needed.
- Decides a **tier** per output — `allow / edit / flag / block` — driven by a per-use-case policy.
- Logs every decision to an **immutable, version-stamped audit trail**.

The grading vertical (GradeOps) is the concrete demo: it reads scanned handwritten exams, redacts student identifiers, grades against a rubric with partial credit, and routes uncertain grades to a human review dashboard.

---

## What Round 2 added on top of GradeOps

| Area | GradeOps (Round 1) | ControlPlane.ai (Round 2) |
|---|---|---|
| Determinism | temperature unset (stochastic) | explicit temp 0, reproducible |
| Grounding | LLM critic only | HHEM-2.1-Open faithfulness score + deterministic citation verifier + cross-model critic |
| Decisions | pass/fail | tiered allow / edit / flag / block |
| Policy | one rubric | JSON policy layer, 3 use-case configs |
| Scope | exam grader | general checker via `POST /api/check` |
| Privacy | fixed top-strip mask (missed angled photos) | vision-based PII detection + redaction anywhere on the page |
| Confidence | multi-pass variance | composite uncertainty (HHEM + rules + critic + flags) |
| Cost | 2 vision calls/crop, frequent rate-limit breaks | 1 vision call/crop, free CPU grounding, throttled |

---

## Architecture

```
Input: exam answer or any AI output + context
         │
    ┌────▼────┐
    │Extractor│  vision · Gemini · temp 0
    └────┬────┘
         │ transcript + claims
    ┌────▼────────┐
    │   Scorer    │  text · model A · temp 0
    └────┬────────┘
         │ per-criterion scores
    ┌────▼─────────┐
    │  Justifier   │  text · model A · temp 0
    └────┬─────────┘
         │
    ┌────▼──────────────────────────────────┐
    │         Verifier (DETERMINISTIC)      │
    │  Citation rule check + HHEM-2.1-Open  │
    └────┬──────────────────────────────────┘
         │
       Gate ◆ ─── borderline ──► LLM Critic (model B, cross-model)
         │
    ┌────▼──────────────────────────────────┐
    │  Pillar checks: Privacy · Bias        │
    │  Policy layer (JSON per use-case)     │
    └────┬──────────────────────────────────┘
         │
    ┌────▼──────────────┐
    │  Decision engine  │  allow / edit / flag / block
    └────┬──────────────┘
         ├──► Audit log (immutable, version-stamped)
         └──► Review queue (sorted by composite uncertainty)
```

Green nodes are deterministic (CPU, no API), blue are LLM calls, orange is the governance layer. The gate runs cheap deterministic checks first and only invokes the LLM critic on borderline cases — protecting both latency and free-tier quota.

---

## The grading vertical (GradeOps pipeline)

```
Scanned PDF / photo
  → Split pages (PyMuPDF)
  → Detect + crop answer region
  → Redact PII (vision detection)
  → Grade (cascade above)
  → Aggregate + uncertainty
  → Plagiarism (cosine similarity)
  → Review queue + audit log
```

---

## Features

- **General checker API** — `POST /api/check` runs grounding + PII + bias over any output and returns a tiered decision under a chosen policy.
- **Grounding (hallucination)** — HHEM-2.1-Open faithfulness scoring on CPU (no API), plus a deterministic verifier that checks every awarded point cites a real claim.
- **Privacy** — vision-based detection and redaction of name / roll / date / email anywhere on a page, before any external call.
- **Bias** — output-side bias scanning plus similarity-as-fairness (near-identical answers scored differently get flagged).
- **Tiered decisions + policy layer** — three use-case configs (customer support, internal knowledge, decision support) with different risk tolerances.
- **Deterministic + auditable** — temperature 0, reproducible, every decision stamped with rubric / prompt / model versions.
- **Review dashboard** — side-by-side answer + AI grade, sorted by uncertainty, keyboard shortcuts (Enter / O / F / J / K).
- **Plagiarism** — cosine similarity over transcripts using sentence-transformers.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS |
| Backend | FastAPI, Python |
| Agentic AI | LangGraph, LangChain |
| LLM (default) | Gemini 3.6 Flash (per-role routing; swap text/critic to Groq or Claude via env) |
| Grounding | HHEM-2.1-Open (Vectara), CPU |
| OCR / vision | Gemini Vision (hosted) |
| Plagiarism | sentence-transformers/all-MiniLM-L6-v2 |
| PDF Ingestion | PyMuPDF |
| Database | SQLAlchemy + SQLite (dev) / PostgreSQL (prod) |
| Deployment | Hugging Face Spaces (Docker) |

---

## Quick Start

```bash
# 1. Clone and set up
git clone https://github.com/samsadar236/controlplane-pandas.git
cd controlplane-pandas
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Set GOOGLE_API_KEY at minimum.
# For all-Gemini setup (no Groq key):
#   TEXT_PROVIDER=google
#   CRITIC_PROVIDER=google

# 3. Run backend
uvicorn backend.main:app --reload --port 8000

# 4. Frontend dev server (optional)
cd frontend && npm install && npm run dev
```

Try the general checker:

```bash
curl -X POST http://localhost:8000/api/check \
  -H "Content-Type: application/json" \
  -d '{"use_case":"decision_support","output":"The capital of France is Berlin.","context":"Its capital is Paris."}'
# -> tier: block, grounding risk high
```

---

## Environment Variables

```env
LLM_PROVIDER=google
GOOGLE_API_KEY=AIzaSy...
GRADER_MODEL_GOOGLE=gemini-3.6-flash

TEXT_PROVIDER=google
CRITIC_PROVIDER=google
GROQ_API_KEY=

GRADER_TEMPERATURE=0.0
GRADER_NUM_PASSES=1
GRADER_CRITIC_RETRY=0
LLM_MIN_GAP_SECONDS=4.5

HHEM_ENABLED=true
HHEM_HIGH_THRESHOLD=0.7
HHEM_LOW_THRESHOLD=0.4

OCR_BACKEND=hosted
DATABASE_URL=sqlite:///./gradeops.db
STORAGE_ROOT=./storage
PLAGIARISM_THRESHOLD=0.82
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

---

## Project Structure

```
controlplane-pandas/
├── backend/
│   ├── main.py               FastAPI app (serves frontend in prod)
│   ├── checker.py            General "check any output" entrypoint
│   ├── checker_api.py        /api/check + /api/policies routes
│   ├── confidence.py         Composite uncertainty scoring
│   ├── fairness.py           Similarity-as-fairness flags
│   ├── checks/               grounding / PII / bias checks
│   ├── policy/               3 use-case policy configs + loader
│   ├── decision/             Tiered decision engine
│   ├── grader/
│   │   ├── graph.py          LangGraph cascade
│   │   ├── nodes.py          Extractor / Scorer / Justifier / Critic
│   │   ├── cascade.py        Deterministic verifier node + gate
│   │   ├── grounding.py      HHEM faithfulness scoring
│   │   ├── rules.py          Deterministic citation verifier
│   │   ├── llm.py            Per-role LLM factory
│   │   └── rate_limit.py     Global throttle (free-tier safe)
│   ├── ingestion/            PDF split, crop, vision-based PII redaction
│   └── ocr/                  Hosted vision adapter
├── frontend/
│   └── src/pages/            Landing / Rubrics / Grading / Review / Audit
├── data/eval/                Eval sets and gold scores
└── scripts/                  eval harness, pregrade, db init
```

---

## API Endpoints

| Endpoint | Description |
|---|---|
| `POST /api/check` | Run the checker over any AI output; returns a tiered decision |
| `GET /api/policies` | List the use-case policies |
| `GET /api/health` | Provider + per-role model + OCR backend status |
| `POST /api/papers/upload` | Grade an exam paper (the vertical demo) |
| `GET /api/review/queue` | Review queue, sorted by uncertainty |
| `GET /api/audit` | Immutable decision log |
| `GET /api/stats` | Dashboard metrics |
| `GET /docs` | Full Swagger UI |

---

## Deployment (Hugging Face Spaces)

Docker SDK Space. Set `GOOGLE_API_KEY` as a Space secret. For demo reliability, a pre-graded `gradeops.db` is baked into the image so the Audit and Review pages show real data on cold start.

**Live:** [samruddhisadar-gradeops.hf.space](https://samruddhisadar-gradeops.hf.space)

---

## Lineage

ControlPlane.ai is the Round 2 evolution of GradeOps ([github.com/samsadar236/gradeops](https://github.com/samsadar236/gradeops)). The commit history of this repository includes the full GradeOps lineage followed by the ControlPlane generalization, so the progression is on the record.
