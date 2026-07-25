# PocketTaste — creator intelligence & discovery layer

A FastAPI backend that turns a content catalog and a listener event log into four
things: **personalised recommendations**, **creator demand intelligence**,
**duplicate/plagiarism screening**, and a **story copilot** that refuses to help you
write something the catalog already has.

It is an *independent layer*. It does not replace, wrap, or depend on any
platform-side recommender. That framing is deliberate — see
[Positioning](#positioning-what-this-is-and-is-not).

---

> **Just want to run it?** See [RUNNING.md](RUNNING.md) — server startup, when the
> recommendation system engages, and how Databricks fits in.

## Quick start

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

copy .env.example .env      # then fill in DB_URL (and OPENAI_KEY if you have one)

.\.venv\Scripts\python.exe -m scripts.seed --reset     # import the real catalog + run the pipeline
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/docs>.

Seeding flags: `--source stories|synthetic` (default `stories`), `--no-llm`
(heuristic labels, zero API spend), `--no-pipeline` (load data only), `--users N`,
`--seed N`.

### Where the data comes from

The default source is the platform's **real catalog** — the `stories` collection in
the `Click` database: 100 audio series across 10 genres in Hindi / Hinglish /
English, with real plays, likes, ratings, episode counts, authors and narrators.
That collection is strictly **read-only**; the importer maps it into `content_items`
and never writes back to it.

What it does not contain is a per-listener event log — it records aggregate totals,
and the feature builder needs individual play / replay / drop-off events *with
positions* to compute retention curves. So the event stream is reconstructed and
**calibrated against the real aggregates**:

| calibrated from | drives |
|---|---|
| real `plays` (√-compressed) | how many listeners each story gets |
| real `rating` | how likely a listener is to finish it |
| real `likes / plays` | replay and revisit propensity |

Square-root rather than linear, because real play counts span ~70× across this
catalog and a linear map would leave the tail titles with one listener each — too
few for a retention curve to mean anything.

So relative demand between the 100 titles is meaningful, while individual listener
behaviour is not real. That distinction gets its own provenance value —
`simulated_from_real_catalog` — deliberately neither `real` nor
`synthetic_simulation`. See [Honesty guarantees](#honesty-guarantees).

`--source synthetic` switches to a fully invented catalog *and* event log. It is what
the duplicate-gate demonstration uses, since the real catalog contains no re-uploads
to catch.

**No OpenAI key?** Everything still runs. Embeddings fall back to a deterministic
hashed bag-of-n-grams and labels fall back to keyword heuristics. `GET /health`
always reports which backend is live, and every generated label carries a
`label_source` of `llm` or `heuristic`.

---

## Accounts and real listening data

Real people sign in, and their listening is recorded against their account. That is
what turns the log from a simulation into evidence.

```powershell
.\.venv\Scripts\python.exe -m scripts.onboard_users     # creates the launch accounts
.\.venv\Scripts\python.exe -m scripts.onboard_users --list
```

```bash
POST /auth/register     # email + password -> bearer token
POST /auth/login        # -> bearer token
GET  /auth/me           # the signed-in account
GET  /auth/scheme       # how auth is configured here

POST /activity          # logged against the token holder
POST /activity/batch
GET  /me/profile        # your derived taste profile
GET  /me/history        # your own event log
POST /me/recommendations
```

**Passwords** are hashed with **scrypt** (n=16384, r=8, p=1, 16-byte per-password
salt) from the standard library — memory-hard, so it resists GPU cracking in a way
PBKDF2 does not. The hash is self-describing (`scrypt$n$r$p$salt$key`), so the cost
can be raised later without invalidating existing credentials. Plaintext is never
stored, logged, or returned.

**Tokens** are HS256 JWTs carrying only subject and issue/expiry — no personal data
in the payload. Set `JWT_SECRET` in `.env`; without it a random key is generated per
process and every token dies on restart, which `/auth/scheme` and `/health` both
warn about.

Three properties the tests pin:

- **`user_id` is never accepted from a request body** on `/activity`, `/activity/batch`
  or `/me/*`. It comes from the token. Sending one is a 422, so no caller can write
  events into someone else's listening history.
- **Login gives the same error** for an unknown email and a wrong password, and still
  runs a hash comparison when no account exists — otherwise wording and response
  timing turn the endpoint into an account-enumeration oracle.
- **`password_hash` cannot leave the service.** Every outbound payload goes through
  `UserAccount.public()`, and `AccountResponse` has no field for it.

Uploads (`POST /catalog`) and copilot drafts are attributed to the signed-in creator,
so a story cannot be filed under someone else's name.

### Real events vs simulated ones

Both live in the same log and are never conflated. Authenticated events are written
with `is_synthetic=False`; the calibrated simulator writes `is_synthetic=True`.
`GET /activity/stats` reports the split, and provenance flips to `mixed` the moment
real activity lands. Once there is enough genuine traffic:

```powershell
.\.venv\Scripts\python.exe -m scripts.seed --purge-simulated
```

drops every simulated event and rebuilds features on real activity alone.

---

## The five-minute tour

```bash
POST /pipeline/run                 # build embeddings, features, demand report
POST /recommendations              # ranked results with a full score breakdown
POST /similarity/check             # screen a draft before upload
GET  /insights/opportunities       # under-served genre/language cells
POST /evaluation/run               # Recall@K / NDCG@K vs popularity and random
POST /copilot/outline              # screened, demand-anchored story outline
GET  /system/architecture          # weights, thresholds, and what is excluded by design
```

---

## Architecture

```
                 ┌──────────────────────── online (FastAPI + MongoDB) ───────────────────────┐
  events ──────► │ /activity ──► activity_events                                             │
                 │                                                                            │
  catalog ─────► │ /catalog ──► [similarity gate] ──► content_items                          │
                 │                                                                            │
  listener ────► │ /recommendations ──► candidate gen ──► 7-signal scorer ──► MMR ──► explain │
                 │ /discovery/search ──► Haystack: BM25 + dense ──► RRF ──► generator         │
                 │ /insights/*       ──► demand segments, saturation, briefs                  │
                 └────────────────────────────────┬───────────────────────────────────────────┘
                                                  │
                 ┌────────── agent pipeline (POST /pipeline/run) ──────────┐
                 │ 1. content_intelligence  embed, label, cluster, score   │
                 │ 2. ingestion             events ──► features + profiles │
                 │ 3. insight               features ──► demand + briefs   │
                 └─────────────────────────────────────────────────────────┘
                                                  │
                 ┌──────── batch tier (Databricks, optional) ──────────────┐
                 │ embedding refresh · clustering · all-pairs sweep · eval  │
                 └─────────────────────────────────────────────────────────┘
```

### Layout

```
app/
  core/         config, logging, errors, clock          — no dependencies on anything below
  domain/       enums, persisted models, API DTOs       — pure data, no IO
  data/         Mongo gateway + one repo per aggregate  — the only code that talks to Mongo
  services/     one module per capability               — all IO injected via the constructor
  agents/       3 agents + orchestrator
  pipelines/    Databricks batch-tier specification
  api/          thin routes: validate, delegate, shape
  container.py  the composition root — the only place the graph is wired
```

Routes never build a service, services never build a repository, repositories never
build a client.

---

## The recommendation engine

Three stages. No trained model — that is a choice, not a shortcut. With a
hackathon-sized log a learned ranker would overfit, and a score a creator cannot
interrogate is useless to them. Every number below is reproducible by hand.

**1. Candidate generation** — union of three sources so no single failure mode
collapses the pool:
- dense neighbours of the listener's taste vector
- item-item co-occurrence neighbours of what they already finished
- an exploration slice of under-observed titles

**2. Scoring** — a linear blend of seven signals. Weights are published at
`GET /recommendations/weights` and returned with every response; `contributions`
sums exactly to `relevance_score`.

| signal | weight | what it measures |
|---|---|---|
| `affinity` | 0.30 | cosine(taste vector, item embedding) |
| `co_occurrence` | 0.20 | popularity-normalised item-item co-occurrence |
| `retention` | 0.18 | measured completion / drop-off / re-engagement / replay |
| `genre_affinity` | 0.10 | learned genre affinity blended with language match |
| `freshness` | 0.08 | exponential decay, 30-day half-life |
| `originality` | 0.07 | `1 - duplicate_risk`, so re-uploads cannot crowd out originals |
| `exploration` | 0.07 | UCB1-style optimism for under-observed items |

**3. MMR re-selection** — `λ·relevance − (1−λ)·max_similarity_to_already_selected`.
Without it a good taste vector returns seven variants of the same story.

**Duplicate suppression.** Within a duplicate family the earliest publication is
kept and later copies are withheld from ranking, so a re-uploader cannot harvest
impressions the original creator earned. The count is reported in every response,
never silently applied.

### Engineering decisions worth defending

- **Co-occurrence is cosine-normalised** — `|A∩B| / √(|A|·|B|)`. Raw co-counts let
  blockbusters dominate every neighbour list.
- **`cosine()` clamps to [0,1] rather than rescaling from [-1,1].** Modern text
  embeddings are almost never negatively correlated; unrelated passages sit around
  0.15 raw. Rescaling maps that to 0.57 and pushes related pairs to 0.85+, which
  collapses the gap between "unrelated" and "duplicate" and makes every threshold in
  the system meaningless. This was measured, not assumed: rescaling produced **30
  false near-duplicate flags on a 41-item catalog**; clamping produced **zero**.
- **Language is a partial hard preference.** A Hindi-only listener will not finish an
  English story however well it matches semantically.
- **Early abandons are weighted more negatively than late ones.** Bailing at 5% is a
  much stronger statement than stopping at 85%.
- **The serving cache** holds catalog, profiles, features and the co-occurrence
  matrix in memory, refreshed on pipeline completion and on TTL. Reading all of that
  from Mongo per request would be absurd.

---

## The similarity / plagiarism gate

The brief's motivating case: *Solo Leveling*, *Solo Leveling Season 3*, and
*Solo Leveling: The End* are three uploads of the same audio under different names.

Six independent signals, reported separately so a reviewer can see **why** something
matched — different signals imply different kinds of copying:

| signal | weight | catches |
|---|---|---|
| `narrative_arc` | 0.34 | same story after paraphrasing and renamed characters |
| `semantic` | 0.26 | same meaning after rewording or translation |
| `lexical_shingle` | 0.16 | verbatim copy-paste (5-gram Jaccard) |
| `title` | 0.10 | identical title after stripping season/part/language markers |
| `description` | 0.08 | reused blurb |
| `chapter_structure` | 0.06 | re-packaged episode layout |

**Why two embeddings per item.** `embedding` covers surface semantics.
`arc_embedding` covers only the *narrative fingerprint* — an LLM-extracted skeleton
(premise with proper nouns stripped, protagonist archetype, central conflict,
setting, progression system, resolution shape). Surface embeddings drift when a
plagiarist paraphrases; the story skeleton does not.

Measured on the seeded catalog, against a re-upload rewritten heavily enough to
defeat verbatim detection:

```
lexical_shingle  0.099   <- verbatim detection misses it entirely
narrative_arc    0.924   <- the arc signal catches it
semantic         0.933
                 -> near_duplicate, routed to review
```

**Signal applicability.** A creator screening a one-paragraph premise has no
transcript and no chapter markers, so `lexical_shingle` and `chapter_structure` are
structurally zero. Leaving them in the blend silently penalises the draft for being
early — a verbatim copy of an existing premise scored 0.35 and passed as `clear`.
The gate now drops inapplicable signals and renormalises the remaining weights;
`applied_signals` is reported on every response.

**Verdicts.** `block` ≥ 0.88 combined, or any confirmed exact duplicate / series
variant. `review` ≥ 0.72, or a near-duplicate, or a normalised-title collision — two
unrelated stories are allowed to share a title, but a human should look. Otherwise
`clear`.

A `block` is a stop pending human review, never an automated plagiarism ruling. That
disclaimer is attached to every report.

**Scaling.** Comparing a new upload against the whole catalog is O(n) expensive
pairwise work. Retrieval narrows it to the plausible matches first, then the
expensive per-signal comparison runs on that shortlist.

---

## Demand discovery

The unit of analysis is a market cell: `(genre, language)`.

```
opportunity_score = (demand_share − supply_share) × (1 − duplicate_density)
```

Subtracting shares rather than dividing keeps the number bounded in [-1, 1] and
readable: `+0.089` means the cell absorbs 8.9 percentage points more attention than
its share of the catalog. The saturation factor discounts cells already full of
near-duplicate re-uploads — demand there is being met badly, not left unserved.

`execution_gap = demand_share × drop_off_rate` separates a *different* opportunity:
the audience is already there and the existing execution is losing them.

**Zero-result searches are the strongest signal available** — a listener asked for
something the catalog could not serve. They are weighted at `UNMET_SEARCH_WEIGHT`
(default 3.0) against a play's 0.30, because a failed search is an explicit ask.
Devanagari and other Indic-script queries are attributed via a native-term lexicon;
an English keyword list cannot match `हिंदी क्राइम थ्रिलर`, and silently dropping those
searches would hide exactly the unmet demand being looked for.

Searches that cannot be confidently placed in a cell are **counted and reported
separately, never guessed into a segment**.

---

## Offline evaluation

`POST /evaluation/run` — **global temporal holdout at 80% of the event stream**, not
random leave-one-out.

Random leave-one-out leaks the future into the features: an item's completion rate
computed over the whole log already encodes the interaction you are trying to
predict. User profiles, content features and the co-occurrence matrix are all
rebuilt from the training slice alone. Content embeddings are shared across slices —
they are text-derived and carry no post-split information.

Measured on the **real catalog** (100 stories, 400 listeners, ~18.7k events, 202
evaluable users, k=10):

| strategy | Recall@10 | NDCG@10 | MRR | coverage | novelty |
|---|---|---|---|---|---|
| **hybrid + MMR** | **0.298** | **0.170** | **0.162** | **0.95** | 6.73 |
| popularity | 0.109 | 0.059 | 0.055 | 0.15 | 5.72 |
| random | 0.156 | 0.070 | 0.057 | 1.00 | 6.86 |

Lift over popularity: **+174% Recall@10, +189% NDCG@10, +193% MRR**, at
**6.3× the catalog coverage** — the popularity baseline reaches 15% of the catalog,
the hybrid ranker reaches 95%.

> What these numbers do and do not show. The ranking, the split and the metrics are
> all real computation. The *ground truth* is a simulated event stream, so what is
> being verified is that the ranker recovers taste structure that the simulator put
> there via real popularity and rating data. That is a genuine test of the pipeline,
> and it is not the same as measuring accuracy against real listeners. The report
> states this in its own `caveats` field, and carries
> `provenance: simulated_from_real_catalog`.
>
> Note random beats popularity on Recall here. With 100 items and k=10 random draws
> 10% of the catalog, while popularity keeps recommending the same 15 blockbusters to
> everyone. That is exactly the failure an unreported baseline would hide.

---

## Discovery (Haystack)

```
query ─┬─► BM25 retriever      ─┐
       └─► dense retriever     ─┴─► reciprocal rank fusion ─┬─► prompt ─► generator
                                                            └─► documents (similarity shortlist)
```

**Why Haystack rather than hand-rolled retrieval:** the same retrieval graph serves
two consumers with different tails — conversational discovery (with a generator) and
the plagiarism gate (documents only). One index, one fusion policy, and the
retrievers can be swapped for a managed vector store without touching either caller.

**Why reciprocal rank fusion rather than score averaging:** BM25 scores and cosine
scores are not on a comparable scale. Averaging lets whichever retriever has the
larger numeric range silently dominate. RRF combines ranks, so neither can swamp the
other.

Implemented on `AsyncPipeline` with a custom `@component` embedder, so the query and
the indexed documents always go through the same backend.

---

## The three agents

Three, deliberately. Each owns one stage, has one reason to fail, and reports what
it processed. More agents would add coordination surface without adding capability.

| order | agent | does | LLM |
|---|---|---|---|
| 1 | `content_intelligence` | embed, label, cluster on narrative arc, score originality, rebuild the index | yes |
| 2 | `ingestion` | events → retention curves, chapter interest, abandon points, taste vectors | **no** |
| 3 | `insight` | features → demand segments, pattern saturation, creator briefs | yes |

**Stage order is fixed by data dependency, not preference.** Content intelligence
runs first because taste vectors are weighted means of content embeddings.

The ingestion agent is entirely deterministic — no LLM, no sampling, no randomness.
The same log always produces the same features. That is the only reason the
creator-facing metrics can be defended.

A failed stage does not abort the run; later stages execute on what is already
persisted and the run is marked `partial` so the failure is visible.

---

## Databricks (optional)

Not on the online request path, and nothing breaks without it.
`GET /pipeline/databricks` emits a Jobs 2.1 job specification plus a Unity Catalog
table plan for the batch tier: embedding refresh, full-catalog clustering, all-pairs
similarity sweep, feature aggregation, ranker evaluation. Without credentials it is a
deployable artifact rather than a live integration, and `configured: false` says so.

---

## Sarvam AI

Provider strategy for Indic languages, off by default. Set `SARVAM_API_KEY` and
generations for `SARVAM_LANGUAGES` route to Sarvam instead of OpenAI; everything else
keeps going to OpenAI. `GET /health` reports which languages are routed.

---

## Story copilot — real GOAT integration

Outlining runs on the actual
[GOAT-Storytelling-Agent](https://github.com/GOAT-AI-lab/GOAT-Storytelling-Agent)
package, installed from source. Its staged pipeline executes upstream and
unmodified:

```
init_book_spec  ->  create_plot_chapters  ->  enhance_plot_chapters
   8-field spec        three-act plan            act-by-act refinement
```

GOAT's own `prompts.py`, `parse_book_spec` and `Plan.parse_text_plan` do the work.
One prompt for a whole outline drifts — later chapters contradict earlier ones —
and GOAT's staging is the fix: each stage sees the committed output of the previous.

**What we changed, and why.** Upstream targets a self-hosted GOAT-70B behind a
HuggingFace TGI or llama.cpp server, which is not available here. Every model call
in `StoryAgent` funnels through one method, `query_chat(messages)`, so
`app/services/goat_agent.py` subclasses the agent and overrides exactly that,
routing to OpenAI. We supply the transport; GOAT supplies the craft.

Two implementation details worth knowing:

- We pass `backend="llama.cpp"` — not because we speak llama.cpp (`backend_uri` is
  never used) but because `backend="hf"` eagerly downloads a `LlamaTokenizerFast`
  from the Hub in `__init__`. The llama.cpp branch skips that, and since
  `query_chat` is replaced outright, no llama.cpp code path is reached either.
- GOAT is synchronous; FastAPI runs it in a worker thread so the event loop keeps
  serving.

`GET /copilot/engine` reports whether GOAT is actually driving. If the package or
the API key is missing, the service falls back to direct staged prompts and says so
in `generated_by` rather than pretending GOAT ran.

Two things make this more than a GOAT wrapper:

1. **The premise is screened before anything is written.** There is no point
   outlining eight chapters of a story that will be blocked at upload.
2. **The outline is anchored to a measured demand segment**, so the creator sees the
   supply/demand position of what they are about to write, plus the over-supplied
   narrative patterns to avoid.

---

## Honesty guarantees

The brief was explicit that nothing may be fabricated. Enforced structurally:

- **`provenance` on every aggregate**, resolved in one place from *two* independent
  facts — is the catalog real, and is the event stream real:

  | value | means |
  |---|---|
  | `real` | real catalog, real logged events |
  | `simulated_from_real_catalog` | the platform's real catalog and real plays/likes/rating; event stream reconstructed and calibrated to them |
  | `synthetic_simulation` | catalog and events both invented by the built-in simulator |
  | `mixed` | any blend — filter before using |

  The middle state exists because collapsing it into either neighbour would lie in
  one direction or the other. Each state carries a written disclosure that travels
  with the report body, not just the enum.
- **`confidence` and `sample_size` on every metric row**, from a configurable
  threshold.
- **`label_source` on every generated label** — `llm` or `heuristic`. A fallback can
  never be mistaken for a model output.
- **The LLM never chooses a number.** Scores, verdicts and drop-off points are all
  computed upstream; the LLM only turns computed numbers into prose, under a system
  prompt that forbids inventing statistics. Every explanation reports its
  `explanation_source`, and there is a deterministic fallback for all of them.
- **`InsufficientDataError` instead of a guess** when the sample is empty.
- **Unattributable searches are counted, not assigned.**
- **The evaluation report writes its own caveats**, including that its data is
  synthetic and that Recall@K is optimistic on a small catalog.

### What the real catalog produces

Run against the 100 real stories, the pipeline finds gaps that are actually in the
data rather than planted ones:

| finding | evidence |
|---|---|
| `thriller/hi` under-served | 6 titles, 117 listeners, 25 searches the catalog could not answer |
| `comedy-slice-of-life/hi` under-served | **1** title against 27 unanswered searches |
| zero duplicate false positives | all 100 titles distinct; the gate flags nothing, correctly |
| romanized-Hindi discovery works | *"koi darawni haveli wali bhoot ki kahani"* → the Hinglish horror shelf |

The duplicate gate finding nothing on this catalog is the point: it does not
manufacture a result to look useful. To see it fire, `--source synthetic` plants a
family for it to catch.

### Synthetic mode

`--source synthetic` builds a catalog *and* event log with specific, recoverable
structure rather than noise: latent per-listener taste, a deliberately under-supplied
`thriller/hi` cell attracting zero-result searches, a duplicate family (verbatim
re-upload, season variant, heavy paraphrase), and one title with a mid-runtime
chapter that bleeds listeners.

Everything it writes carries `is_synthetic=True`, and the tag survives to the API.
Fully seeded — the same seed always yields the same catalog, events, and metrics.

The pipeline recovers all four planted structures:

| planted | recovered |
|---|---|
| under-supplied `thriller/hi` | ranked #1 opportunity, `+0.089`, 89 zero-result searches |
| duplicate family (4 items) | all 4 flagged; the 2 verbatim re-uploads suppressed, the original kept |
| heavy paraphrase | caught at arc 0.924 with shingle at 0.099 |
| weak mid-runtime chapter | retention curve falls 0.67 → 0.33 across the midpoint |

Risk separation across the 41-item catalog: p50 `0.576`, p90 `0.663`, max `0.996`.

Typically one or two additional same-genre pairs are tagged `near_duplicate` around
`0.66` — LLM fingerprint extraction is not deterministic, and two romance stories
built on the same premise genuinely do converge on the arc embedding. That is a
*review* label, not a block: it sits below the 0.72 review threshold at screening
time and never suppresses anything. Run with `--no-llm` for fully deterministic
heuristic labelling.

---

## Positioning: what this is and is not

**Is:** an explainable content-intelligence layer that captures listener behaviour,
discovers content demand, screens for duplicate and plagiarised stories, and produces
creator-facing recommendations using semantic retrieval and LLM reasoning.

**Is not:** a replacement for a production recommender trained on years of real data.

Excluded by design, and reported at `GET /system/architecture`:

- no fine-tuning — the log is far too small to justify it
- no trained ranker — an unexplainable score is useless to a creator
- no claim to beat an established production recommender
- no synthetic figure ever presented as real audience truth

---

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

127 tests, no network and no database required — they pin feature arithmetic,
retention-curve monotonicity, title normalisation across seven series-marker
patterns, gate verdicts, MMR diversity behaviour, duplicate suppression, demand
attribution, evaluation metric bounds, the upstream story mapping, the GOAT
subclass surface, password hashing and token handling (including the `alg: none`
JWT bypass), and the API contract — that every storage-backed route degrades to a
clean 503 rather than a stack trace, and that every route which writes on someone's
behalf is guarded.
