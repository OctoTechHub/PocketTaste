# PocketTaste

An AI creator-intelligence and discovery layer for long-form audio stories.
**Backend only, FastAPI.**

It takes a content catalog plus a listener event log and produces:

- **Recommendations** — hybrid ranking with a full, auditable score breakdown
- **Creator demand intelligence** — which genre/language cells are under-served, and why
- **Plagiarism screening** — six-signal duplicate detection that survives paraphrasing
- **A story copilot** — staged outlining that refuses to help write something the catalog already has

Stack: **FastAPI + MongoDB + Haystack + OpenAI**, with an optional Databricks batch
tier and optional Sarvam AI routing for Indic languages.

---

## Where things are

```
server/           the entire backend
  app/            core · domain · data · services · agents · pipelines · api
  scripts/        seed - onboard_users - clean_data
  tests/          127 tests, no network or database required
  README.md       full documentation — start here
```

**→ [`server/RUNNING.md`](server/RUNNING.md)** — how to run it, when the
recommendation system engages, and how Databricks is used.

**→ [`server/README.md`](server/README.md)** — architecture, ranking and similarity
formulas, measured evaluation results, honesty guarantees.

---

## Run it

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env          # fill in DB_URL, and OPENAI_KEY if you have one
.\.venv\Scripts\python.exe -m scripts.seed --reset          # import the real catalog
.\.venv\Scripts\python.exe -m scripts.onboard_users            # create accounts
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Then open <http://127.0.0.1:8000/docs>.

Runs without an OpenAI key: embeddings fall back to deterministic hashing and labels
to keyword heuristics. `GET /health` always reports which backend is live.

---

## What it claims, and what it does not

**Claims:** an explainable content-intelligence layer that captures listener
behaviour, discovers content demand, screens for duplicate and plagiarised stories,
and produces creator-facing recommendations using semantic retrieval and LLM
reasoning.

**Does not claim:** to replace a production recommender trained on years of real
data. It is an independent layer that sits alongside one.

The seeded dataset is synthetic. Every aggregate response carries a `provenance`
field, and a report built from seeded data says so in its own body.
