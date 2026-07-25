# PocketTaste · API (FastAPI)

Multi-stage recommendation + conversational discovery for long-form audio.

## Layered architecture (separation of concerns)

```
app/
  domain/     # pure: models, vocab, scoring math — no IO, no framework
  data/       # MongoDB repositories (only layer that knows about pymongo)
  services/   # business logic
    ai/       # embeddings + LLM (OpenAI, with deterministic local fallback)
    taste_service.py          # Stage 0: behavior -> taste profile / vector
    candidate_service.py      # Stage 1: content + collaborative + popularity
    ranking_service.py        # Stage 2: transparent feature scorer
    discovery_service.py      # Stage 3: NL intent -> semantic + personalized rank
    explain_service.py        # Explain-Why (grounded template + optional LLM)
    recommendation_service.py # assembles the home-feed rails
    context_service.py        # in-memory catalog + co-occurrence cache
  api/        # thin controllers (routes.py) + serializers + request schemas
scripts/seed.py               # synthetic catalog + persona-driven behavior
```

Dependencies point **inward**: `api → services → data → domain`. `domain` imports
nothing from the outer layers, so the ranking logic is unit-testable in isolation.

## Setup

```bash
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
python -m scripts.seed
uvicorn app.main:app --reload --port 4000
```

`OPENAI_API_KEY` is optional — with it empty the whole system runs in a
deterministic **local-fallback** mode (hash embeddings + heuristic NL parsing), so
the demo never depends on an external service. Add a key to switch to real OpenAI
embeddings + LLM discovery (the `/api/health` `mode` field tells you which is live).
