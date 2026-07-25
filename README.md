# PocketTaste

**AI-driven content discovery & personalization for long-form audio.**
A multi-stage recommendation + conversational-discovery engine that makes every
PocketFM listener's *next series* feel made-for-them — optimizing for **episode
completion and coin unlocks**, not just clicks.

> Hackathon theme 3 — *AI-Driven Content Discovery & Personalization* → the
> **Entertainment Discovery** problem (Mood-First Search, Explain-Why, personalized
> "For You").

---

## What it does

- **Personalized "For You" feed** — themed rails (`Because you finished…`,
  `Coin-worthy binges`, `New & rising in <language>`) ranked to maximize long-form
  engagement and paid unlocks.
- **Mood-first / conversational search** — *"dark office romance, Hindi, 15-min
  episodes, no horror"* → parsed intent → semantic retrieval → personalized re-rank.
- **Explain-Why** — every recommendation carries a grounded, human reason and a
  transparent per-feature score breakdown.
- **Live in-session adaptation** — simulate listening (play / binge / unlock coins /
  drop) and watch the feed re-rank in real time.

## The 3-stage engine

```
 behavior events                                            natural language query
       │                                                              │
       ▼                                                              ▼
┌──────────────┐   ┌───────────────┐   ┌────────────────┐   ┌────────────────────┐
│ Stage 0      │   │ Stage 1       │   │ Stage 2        │   │ Stage 3            │
│ Taste profile│──▶│ Candidate gen │──▶│ Ranking        │──▶│ Conversational +   │
│ (taste vector│   │ content +     │   │ transparent    │   │ Explain-Why (LLM)  │
│  + affinities)│  │ collaborative │   │ feature scorer │   │ intent → re-rank   │
└──────────────┘   │ + popularity  │   │ (completion +  │   └────────────────────┘
                   └───────────────┘   │  coin proxy)   │
                                       └────────────────┘
```

Every stage is explainable and runnable today; each maps cleanly to a production
upgrade (see below).

## Tech stack

| Layer | This repo (live, runnable) | Production scale-up |
|-------|----------------------------|---------------------|
| Backend | **Python · FastAPI** | same |
| Data | **MongoDB Atlas** (behavior + catalog) | + feature store |
| Embeddings / LLM | **OpenAI** (`text-embedding-3-small`, `gpt-4o-mini`) with a deterministic **local-hash fallback** (runs with no API key) | same + fine-tune |
| Stage 1 candidates | content + item-item co-occurrence | **SASRec via RecBole**, served on **NVIDIA Merlin** |
| Stage 2 ranking | transparent linear feature scorer (A/B-tunable weights) | **Merlin DLRM / deep CTR** |
| Stage 3 discovery | OpenAI intent-parse + semantic re-rank | **Haystack** retrieval pipeline |
| Frontend | **Next.js 16 · React 19 · Tailwind v4** | same |
| Offline R&D | **RecBole** benchmark (`/recsys`, arXiv:2302.03561) | same, on cluster |

## Repo structure

```
PocketTaste/
├── server/                 # FastAPI backend (clean layered architecture)
│   ├── app/
│   │   ├── domain/         # pure entities, vocab, scoring math (no IO)
│   │   ├── data/           # MongoDB repositories
│   │   ├── services/       # taste, candidate, ranking, discovery, explain, ai/
│   │   └── api/            # thin controllers + serializers
│   └── scripts/seed.py     # synthetic Pocket-style catalog + persona behavior
├── client/                 # Next.js UI
│   ├── lib/                # typed api client, types, hooks helper, visuals
│   ├── features/           # user / feed / discovery / series / profile (hooks own side-effects)
│   ├── components/         # presentational components
│   └── app/                # page + layout
└── recsys/                 # RecBole offline benchmark (SASRec vs Pop) + Mongo exporter
```

The architecture deliberately follows strict **separation of concerns** — domain →
data → services → api on the backend; typed api-client → feature hooks →
presentational components on the frontend.

---

## Run it

### 1. Backend (FastAPI)

```bash
cd server
python -m venv .venv && .venv/Scripts/activate      # (Windows) ; source .venv/bin/activate on *nix
pip install -r requirements.txt
# edit .env — DB_URL is set; add OPENAI_API_KEY to enable real AI (optional)
python -m scripts.seed            # seeds 30 series + ~52 users + ~2k events
uvicorn app.main:app --reload --port 4000
```

Health check: <http://localhost:4000/api/health> · API docs: <http://localhost:4000/docs>

### 2. Frontend (Next.js)

```bash
cd client
bun install        # or npm install
bun run dev        # http://localhost:3000
```

### 3. RecBole benchmark (optional, separate env)

See [`recsys/README.md`](./recsys/README.md).

---

## API

| Endpoint | Purpose |
|----------|---------|
| `GET /api/feed?user_id=` | personalized rails |
| `POST /api/discover` `{query, user_id?}` | conversational discovery (intent + results) |
| `POST /api/events` | log a behavior signal (drives live adaptation) |
| `GET /api/profile?user_id=` | derived taste profile |
| `GET /api/series/{id}` | series detail + "more like this" |
| `GET /api/explain?user_id=&series_id=` | single LLM explanation |
| `GET /api/users` · `GET /api/health` | demo users · mode/status |

## Notes on the data

There's no public PocketFM dataset, so `scripts/seed.py` generates a
**synthetic-but-realistic** world: a 30-title Pocket-style catalog (Hindi/English +
regional, with genre/tone/pacing/coin metadata) and **persona-driven behavior** so
the recommender has genuine signal — users in the same persona finish overlapping
series (collaborative co-occurrence) and drop mismatched ones (negative signal).
