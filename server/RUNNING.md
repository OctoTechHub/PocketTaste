# Running the backend

Minimal guide: start the server, understand when recommendations become real, and
know exactly what Databricks does here.

For the full design (ranking formulas, similarity signals, honesty guarantees) see
[README.md](README.md).

---

## 1. Start it

```powershell
cd server

# first time only
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env        # then fill in DB_URL, OPENAI_KEY, JWT_SECRET

.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open **<http://127.0.0.1:8000/docs>**.

Check it came up healthy:

```bash
curl http://127.0.0.1:8000/health
```

`status: "ok"` means Mongo is connected. `"degraded"` means it is not — everything
that needs storage will return `503` with a clear message, nothing will crash.

### Required environment

| variable | why |
|---|---|
| `DB_URL` | MongoDB connection string |
| `MONGO_DB_NAME` | `Click` — where `stories` lives |
| `JWT_SECRET` | signs login tokens. Without it a random key is generated per process and **every token dies on restart** |
| `OPENAI_KEY` | optional. Without it embeddings fall back to deterministic hashing and labels to keyword heuristics — the service still runs end to end |

Generate a JWT secret:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## 2. Log in

Four accounts exist. Password for all of them: **`Test@1234`**

```
krish@gmail.com    amogh@gmail.com    nandan@gmail.com    rahul@gmail.com
```

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"krish@gmail.com","password":"Test@1234"}'
```

Take `access_token` from the response and send it on authenticated calls:

```
Authorization: Bearer <access_token>
```

Account management:

```powershell
.\.venv\Scripts\python.exe -m scripts.onboard_users --list
.\.venv\Scripts\python.exe -m scripts.onboard_users --password 'NewPass1234' --set-password
```

---

## 3. Log listening activity

This is the fuel. Nothing downstream exists without it.

```bash
curl -X POST http://127.0.0.1:8000/activity \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"content_id":"blackout","event_type":"play","position_seconds":0,"session_id":"s1"}'
```

Event types: `play, pause, resume, skip, replay, complete, drop_off, chapter_jump,
search, revisit`. Full list with weights at `GET /activity/schema`.

There is no `user_id` field — it comes from your token. Sending one is a `422`.

Use `POST /activity/batch` for up to 5000 at once.

---

## 4. When does the recommendation system actually start?

**Not automatically.** Recommendations are served from state built by the agent
pipeline, and the pipeline only runs when you ask it to.

```bash
curl -X POST http://127.0.0.1:8000/pipeline/run \
  -H "Content-Type: application/json" -d '{}'
```

Three agents run in order — the order is fixed by data dependency, not preference:

| # | agent | produces | needs an LLM |
|---|---|---|---|
| 1 | `content_intelligence` | embeddings, labels, clusters, originality, search index | yes |
| 2 | `ingestion` | retention curves, episode interest, **listener taste vectors** | no |
| 3 | `insight` | demand segments, saturated patterns, creator briefs | yes |

Stage 1 runs first because taste vectors in stage 2 are weighted means of content
embeddings. Stage 3 aggregates what stage 2 produced.

Then:

```bash
curl -X POST http://127.0.0.1:8000/me/recommendations \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"limit":10}'
```

### The honest maturity ladder

| listener state | what you get |
|---|---|
| unknown user, or **fewer than 2 positive interactions** | cold start — ranks on content quality, freshness, originality and exploration. `cold_start: true` |
| **≥2 positive interactions** *and* the pipeline has run since | personalised — taste vector and item-item co-occurrence engage. `cold_start: false` |

**A user's activity does not change their recommendations until the pipeline runs
again.** Profiles are batch-built, not updated per event. Re-run after logging
activity, or on a schedule.

What each endpoint needs:

| endpoint | needs |
|---|---|
| `/recommendations`, `/me/recommendations` | content profiles (stage 1). Works without features — falls back to cold start |
| `/discovery/search`, `/similarity/check` | content profiles (stage 1) |
| `/analytics/content/*` | content features (stage 2) — `404` until then |
| `/insights/*` | content features (stage 2) — `409 insufficient_data` until then |
| `/evaluation/run` | ≥20 events; reports how many users actually qualified |

Cheap partial re-run (skips LLM relabelling, ~5s instead of ~90s):

```bash
curl -X POST http://127.0.0.1:8000/pipeline/run -H "Content-Type: application/json" \
  -d '{"stages":["ingestion_agent","insight_agent"],"use_llm":false}'
```

### Current data state

The database holds **100 real stories**, **100 content profiles**, and **42 real
events** from the 4 accounts. All simulated data has been removed, and the pipeline
has **not** been run since.

So right now, verified:

| endpoint | status today |
|---|---|
| `/me/recommendations` | works, personalised (`cold_start: false`) — the 4 profiles survived the cleanup |
| `/discovery/search` | works |
| `/analytics/content/*` | `404` — no features yet |
| `/insights/demand` | `409 insufficient_data` — no features yet |
| `/evaluation/run` | runs, but only **1 user** qualifies, and it says so in `caveats` |

Run `POST /pipeline/run` to fill in the gaps.

42 events across 4 users is genuinely thin. Even after the pipeline, expect
features on only the ~12 stories those users touched, most demand segments marked
`confidence: low`, and evaluation numbers flagged as directional rather than
significant. That is the system being honest, not broken — log more activity and
re-run.

To restore a large calibrated dataset for demoing:

```powershell
.\.venv\Scripts\python.exe -m scripts.seed --source stories --reset
```

To strip back to real-only again:

```powershell
.\.venv\Scripts\python.exe -m scripts.clean_data --dry-run   # preview
.\.venv\Scripts\python.exe -m scripts.clean_data --apply
```

---

## 5. "Which genre needs more content?"

This is the report the whole pipeline exists to produce.

```powershell
.\.venv\Scripts\python.exe -m scripts.demand_report --refresh
```

```
  GENRES THAT NEED MORE CONTENT
  ----------------------------------------------------------------------
  #1  THRILLER/HI       -> NEEDS MORE CONTENT (1.3x demand vs supply)
        listeners want   ########################..    8.1%
        catalog offers   ##################........    6.0%
        evidence: 6 stories | 117 listeners | 169 plays | 104 completions
                  | 25 searches returned NOTHING
        gap +0.0207  completion 62%  drop-off 38%  confidence HIGH (n=117)
```

It also prints three things a raw opportunity score would not tell you:

- **AUDIENCE IS THERE, BUT THE CONTENT IS LOSING THEM** — high demand *and* high
  drop-off. The market is proven; better execution beats more volume.
- **SEARCHES THAT RETURNED NOTHING** — the literal queries listeners typed that the
  catalog could not answer, e.g. `30x हिंदी सस्पेंस स्टोरी`.
- **OVER-USED STORY PATTERNS** — high catalog share, weak retention. A pattern is
  only judged once at least `MIN_PATTERN_LISTENERS` (default 5) people have heard it,
  because 0% completion on a story nobody has played means *no data*, not *bad story*.

The same verdicts are written into the pipeline log, so a `POST /pipeline/run`
prints them as it goes:

```
[demand] 1. THRILLER/HI  NEEDS MORE CONTENT (demand 8.1% vs supply 6.0% = 1.3x)
         | 117 listeners, 169 plays, 25 searches returned nothing | confidence=high
```

### Seeing it at strength without touching your data

With only 4 listeners every row is honestly labelled `confidence: LOW (n=1)` — true,
but it tells you nothing about whether the analysis works. To see the report as it
reads with a real audience:

```powershell
.\.venv\Scripts\python.exe -m scripts.demand_report --preview-at-scale
```

This simulates a listening population over your real catalog **entirely in memory**.
Nothing is written; your 42 real events stay exactly as they are. The output is
banner-marked `PREVIEW ONLY` and carries `provenance: simulated_from_real_catalog`
so it can never be mistaken for measured traffic.

The same data is available as JSON at `GET /insights/opportunities`.

---

## 6. Background pipeline (continuous, zero AI spend)

The pipeline is batch by nature — profiles are rebuilt from the log, not updated per
event — so it runs on a loop rather than waiting to be triggered.

```bash
GET  /pipeline/scheduler        # status, and exactly what it costs
POST /pipeline/scheduler/tick   # run one beat now (?force=true to ignore the skip)
POST /pipeline/scheduler/stop   # / start
```

**How it costs nothing**, two rules:

1. `use_llm=False`, and only `ingestion` + `insight` run. Both are pure computation
   over data already in Mongo. Insight falls back to its deterministic brief writer,
   disclosed as `heuristic` exactly as always.
2. **It skips when nothing changed.** Each tick compares the event count against the
   last run. No new events, no work — an idle deployment does one
   `count_documents` per interval and stops.

`content_intelligence` — the only stage that embeds and labels, and so the only one
that spends money — is **excluded on purpose**. New uploads get profiled by an
explicit `POST /pipeline/run` or by the Databricks batch tier. A loop should never be
able to run up a bill on its own.

```
BACKGROUND_PIPELINE_ENABLED=true     # default
BACKGROUND_PIPELINE_SECONDS=900      # 15 min
BACKGROUND_PIPELINE_USE_LLM=false    # turning this on WILL spend credits
```

---

## 7. Creator APIs — "what should I write?"

```bash
GET /creator/opportunities   # demand gaps, ranked for you
GET /creator/performance     # how your own stories are retaining
```

`/creator/opportunities` splits the answer in two, because they need different work:

- **`write_more`** — demand outruns supply. The audience is there and under-served.
- **`write_better`** — demand is met in volume but drop-off is high. More of the same
  will not help; the existing execution is losing people.

Segments you already publish in are marked, since extending a shelf you own is a
different bet from entering a new one. Over-supplied narrative patterns come back as
`avoid_patterns`.

---

## 8. Everything else

```bash
POST /discovery/search      # natural-language search (works in Hinglish)
POST /similarity/check      # screen a draft before upload
GET  /insights/opportunities# under-served genre/language cells
POST /copilot/outline       # GOAT-generated outline, screened + demand-anchored
GET  /system/architecture   # weights, thresholds, what is excluded by design
```

---

## 9. How Databricks is used

**Short version: it is the batch tier, and it is deliberately not in the request
path.** The API never calls Databricks. If the workspace is down, unreachable, or
never configured, every endpoint still works.

### Why there is a batch tier at all

Three agents in-process are fine at 100 stories. They stop being fine as the catalog
grows, because three jobs scale badly:

| job | cost | why it cannot stay online |
|---|---|---|
| embedding refresh | one API call per changed item | minutes, not milliseconds |
| catalog clustering | O(n·k) over every profile | full-catalog pass |
| all-pairs duplicate sweep | O(n²) with expensive shingle sets | quadratic |

Online, the similarity gate avoids the quadratic cost by retrieving a shortlist
first. That is the right trade for one upload. It is the wrong trade for auditing
the whole catalog, which is a batch job.

### The split

```
ONLINE   FastAPI + MongoDB     event ingest · ranking · similarity gate · discovery
                               milliseconds, per request
BATCH    Databricks (nightly)  embedding refresh · clustering · all-pairs sweep
                               feature aggregation · ranker evaluation
                               minutes, scheduled
```

MongoDB stays the operational store. Delta is the analytics store.

### What is configured

```bash
curl http://127.0.0.1:8000/pipeline/databricks
```

Returns `configured: true|false`, a **Databricks Jobs 2.1 job specification**, and a
Unity Catalog table plan. Five tasks with their dependency graph:

```
refresh_embeddings ──► rebuild_clusters ──► similarity_sweep
aggregate_features ──┬─────────────────────► evaluate_ranker
rebuild_clusters ────┘
```

Schedule: `0 0 3 * * ?` Asia/Kolkata (nightly, 3am).

### Deploying it — actually deployed

```powershell
.\.venv\Scripts\python.exe -m scripts.deploy_databricks              # dry run
.\.venv\Scripts\python.exe -m scripts.deploy_databricks --apply      # upload + create job
.\.venv\Scripts\python.exe -m scripts.deploy_databricks --status     # job + recent runs
```

The deployer uploads `app/` and `databricks/jobs/` into the workspace, stores the
Mongo URI and OpenAI key in a Databricks secret scope, and creates the job. The
tasks import the **same service code the API runs** — two implementations of a
retention curve would drift and then nobody could say which number was right.

**Current state: deployed and green.** All five tasks succeeded in ~160s, writing
`workspace.pockettaste.{content_profiles, content_clusters, content_features,
evaluation_runs}`.

Four things this workspace forced, all handled in code:

| what happened | fix |
|---|---|
| `Only serverless compute is supported` | the deployer detects the refusal and retries with a serverless job spec (`environments` instead of `job_clusters`) |
| `ERROR_CORE_PACKAGE_VERSION_CHANGE (numpy 1.26.4 -> 2.2.1)` | `haystack-ai` declares unpinned `numpy`, so pip pulled 2.x over a runtime core package and killed the kernel. Haystack is now an **optional import** and omitted from the batch tier — the batch tasks never retrieve, so nothing is lost, and the API keeps Haystack 2.31 |
| `asyncio.run() cannot be called from a running event loop` | serverless executes inside a live loop; tasks now run their coroutine on a worker thread with its own loop |
| `{{secrets/...}}` arriving as a literal string | serverless `spark_python_task` does not interpolate secret refs in `parameters`; tasks resolve them via `dbutils.secrets` instead |

`SystemExit(0)` is also avoided — inside Databricks' IPython kernel even a zero exit
registers as a task failure.

---

## 10. Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

127 tests, no network and no database required.
