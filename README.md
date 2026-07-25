# PocketTaste

An AI layer for long-form audio stories. Backend only. FastAPI.

It does four jobs:

1. It recommends stories to listeners.
2. It tells creators which genre needs more content.
3. It stops duplicate and copied uploads.
4. It helps creators write new stories.

The layer is independent. It does not replace the platform recommender. It works
next to one.

---

## The flow

```mermaid
flowchart TB

    subgraph S1["1 - WHERE DATA COMES FROM"]
        direction LR
        CAT["Click.stories<br/>100 audio series<br/>title, genre, language,<br/>episodes, plays, likes, rating"]
        LIS["Listeners<br/>4 accounts<br/>they sign in and listen"]
    end

    subgraph S2["2 - HOW IT ENTERS - FastAPI"]
        direction LR
        IMP["scripts.seed<br/>reads the catalog<br/>never writes to it"]
        AUTH["POST /auth/login<br/>bearer token"]
        EV["POST /activity<br/>user comes from the token"]
    end

    subgraph S3["3 - WHERE IT IS KEPT - MongoDB"]
        direction LR
        CI[("content_items")]
        AE[("activity_events")]
    end

    subgraph S4["4 - THE PIPELINE - 3 agents in order"]
        direction TB
        A1["AGENT 1 - CONTENT INTELLIGENCE<br/>reads the story text<br/>makes 2 embeddings and the labels<br/>builds the search index<br/>OUT content_profiles"]
        A2["AGENT 2 - INGESTION<br/>reads the events - no AI<br/>retention curves, episode interest<br/>taste vectors, listen sequences<br/>OUT content_features, user_profiles"]
        A3["AGENT 3 - INSIGHT<br/>compares demand with supply<br/>per genre and language<br/>writes the creator briefs<br/>OUT creator_insights"]
        A1 --> A2 --> A3
    end

    subgraph S5["5 - WHAT YOU GET"]
        direction TB
        R1["POST /me/recommendations<br/>8 signals, then MMR"]
        R2["POST /discovery/search<br/>keyword + vector search"]
        R3["POST /similarity/check<br/>6 signals, block or review"]
        R4["GET /creator/opportunities<br/>which genre needs more content"]
        R5["POST /copilot/draft<br/>outline and scene text"]
    end

    subgraph AI["AI PROVIDERS - swap with 2 env vars"]
        direction TB
        OAI["OpenAI<br/>embeddings + chat"]
        DBX["Databricks models<br/>gte-large-en + llama-3.3-70b<br/>included in the workspace"]
        HAY["Haystack<br/>hybrid search index"]
        GOAT["GOAT agent<br/>story writer"]
    end

    subgraph NIGHT["6 - NIGHTLY - Databricks, not in the request path"]
        direction TB
        J1["refresh_embeddings"] --> J2["rebuild_clusters"] --> J3["similarity_sweep"]
        J4["aggregate_features"] --> J5["evaluate_ranker"]
        J2 --> J5
        DELTA[("Delta tables<br/>workspace.pockettaste")]
        J3 --> DELTA
        J5 --> DELTA
    end

    CAT -->|"import, read only"| IMP --> CI
    LIS --> AUTH --> EV --> AE

    CI --> A1
    AE --> A2
    A1 -.->|"profiles"| A2

    OAI -.-> A1
    DBX -.-> A1
    OAI -.-> A3
    DBX -.-> A3
    A1 -.->|"builds"| HAY

    A1 --> R1
    A2 --> R1
    A3 --> R4
    HAY -.-> R2
    HAY -.-> R3
    A1 --> R3
    GOAT -.-> R5
    A3 -.->|"demand context"| R5

    LOOP["Background loop - every 15 min<br/>runs Agent 2 and Agent 3 only<br/>no AI, so no cost<br/>skips when no new events"]
    LOOP -.-> A2

    CI --> NIGHT
    AE --> NIGHT

    classDef src fill:#e8f0fe,stroke:#4285f4,color:#111
    classDef store fill:#fff4e5,stroke:#f59e0b,color:#111
    classDef agent fill:#e9f7ef,stroke:#28a745,color:#111
    classDef out fill:#f3e8fd,stroke:#8b5cf6,color:#111
    classDef ext fill:#fdecea,stroke:#dc3545,color:#111

    class CAT,LIS src
    class CI,AE,DELTA store
    class A1,A2,A3,LOOP agent
    class R1,R2,R3,R4,R5 out
    class OAI,DBX,HAY,GOAT ext
```

Start at `GET /` for the list of all endpoints.

### How one recommendation is built

```mermaid
flowchart LR
    U["Listener<br/>bearer token"] --> P["user_profiles<br/>taste vector<br/>listen sequence"]
    P --> GEN["Pick candidates<br/>from 100 stories"]

    GEN --> SCORE["Score each one"]

    subgraph SIG["8 signals - weights add to 1.0"]
        direction TB
        T["FROM THE TEXT<br/>affinity 0.26<br/>originality 0.07"]
        B["FROM BEHAVIOUR<br/>retention 0.18<br/>co-occurrence 0.14<br/>sequence 0.10<br/>genre affinity 0.10"]
        M["FROM METADATA<br/>freshness 0.08<br/>exploration 0.07"]
    end

    SCORE --> SIG
    SIG --> MMR["MMR<br/>drop near-copies<br/>of what is already picked"]
    MMR --> DUP["Remove re-uploads<br/>keep the first upload"]
    DUP --> OUT["Ranked list<br/>each item shows<br/>its own signal values"]

    classDef sig fill:#e9f7ef,stroke:#28a745,color:#111
    classDef res fill:#f3e8fd,stroke:#8b5cf6,color:#111
    class T,B,M sig
    class OUT res
```

---

## What we use, and why

| Tool | Where | Why |
|---|---|---|
| **FastAPI + MongoDB** | Online | It answers a request in milliseconds. |
| **Haystack** | Search | It runs keyword search and vector search together. It joins the two lists by rank. |
| **OpenAI** | Labels, text | It labels the stories and writes the briefs. It never picks a number. |
| **GOAT** | Copilot | The real package writes the outline and the scenes. |
| **Databricks** | Nightly | It runs the slow jobs. The API never calls it. |
| **Sarvam AI** | Optional | It can write Hindi text. It is off now. |

---

## How the recommender scores a story

Eight signals. Each signal has a published weight. The weights add up to 1.0.

| Signal | Source | Weight |
|---|---|---|
| affinity | story text | 0.26 |
| retention | listener behaviour | 0.18 |
| co-occurrence | listener behaviour | 0.14 |
| **sequence** | listener behaviour | 0.10 |
| genre affinity | listener behaviour | 0.10 |
| freshness | publish date | 0.08 |
| originality | duplicate check | 0.07 |
| exploration | play count | 0.07 |

Behaviour gives 0.52. Text gives 0.33. Text covers a new story that nobody played.

**The sequence signal** asks a different question. Co-occurrence asks "who liked
both?". Sequence asks "what comes next?". For a serial story, the order matters.

The exact pair "A then B" is rare. So the signal uses three steps. It stops at the
first step that gives an answer:

1. We saw "A then B". Use it. Full value.
2. We saw "A then X", and B is like X. Use it. 80 percent value.
3. We saw "crime in Hindi, then suspense in Hindi". Use it. 50 percent value.

Step 3 makes the signal work with few listeners. A real match always beats a guess.

---

## The similarity gate

The gate stops the problem in the brief. One story goes up many times with new
names.

It uses six signals. The strongest one is the **story skeleton**. We ask OpenAI for
the premise, the conflict, and the ending. We remove all the names. Then we embed
that text.

A copy that changes every word keeps the same skeleton.

Our test on a heavy rewrite:

```
  word overlap    0.099   <- a normal copy check finds nothing
  story skeleton  0.924   <- this finds it
```

The gate blocks an exact copy. It also blocks a title match after it removes
"Season 3" or "The End". Other cases go to a person.

---

## The background loop

The pipeline runs every 15 minutes. It costs nothing.

- It runs Agent 2 and Agent 3 only. Both use no AI.
- It skips the run if no new event arrived.
- Agent 1 is not in the loop. Agent 1 costs money. You start it by hand.

---

## Databricks

Databricks is the nightly tier. It is not in the request path. The API works when
Databricks is down.

Five jobs run in this order:

```
  refresh_embeddings --> rebuild_clusters --> similarity_sweep
  aggregate_features -----------------------> evaluate_ranker
```

The jobs import the same code as the API. Two copies of the same maths would drift.

**Status: deployed. All five jobs pass in 160 seconds.** They write four Delta
tables.

---

## Data

| What | Count | Real? |
|---|---|---|
| Stories | 100 | Real. From `Click.stories`. We only read it. |
| Accounts | 4 | Real. |
| Events | 42 | Real. The four users made these. |
| Events | 663 | Simulated. Marked `is_synthetic=true`. |

We never send audio or video. We read the story text and the event rows only.

Every report has a `provenance` field. It says `mixed` now. It tells you what kind
of data made the numbers.

---

## What is done

- [x] Import the real catalog
- [x] Sign-in with email and password
- [x] Event log tied to the account
- [x] Three agents and the pipeline
- [x] Recommender with 8 signals and MMR
- [x] Sequence signal with three-step backoff
- [x] Similarity gate with 6 signals
- [x] Demand report for creators
- [x] GOAT copilot: outline and scenes
- [x] Background loop with no AI cost
- [x] Databricks jobs, deployed
- [x] 139 tests

---

## Limits

Read this before you present.

1. **Four listeners is too few.** Every demand row says `confidence: low`. The
   system reports this itself. It does not hide it.
2. **No transcripts.** The catalog holds a summary, not a script. So we understand
   the metadata. We do not understand the audio.
3. **Episode times are estimates.** We divide the total time by the episode count.
4. **This is not better than NVIDIA Merlin.** Merlin ranks better. Our layer does
   jobs that Merlin does not do.

---

## Run it

See **[server/RUNNING.md](server/RUNNING.md)**.

For the full design, see **[server/README.md](server/README.md)**.
