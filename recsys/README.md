# PocketTaste · RecBole offline benchmark

This folder is the **model-R&D half** of PocketTaste. The live app (`../server`)
serves a fast, explainable feature-ranker; here we benchmark the **sequence-aware
recommenders** (SASRec, GRU4Rec) that would power Stage-1 candidate generation at
production scale — the same family NVIDIA Merlin serves on GPU.

Reference: **RecBole 2.0** — *A Unified, Comprehensive and Efficient Recommendation
Library* (arXiv:2302.03561).

## Why it's separate

RecBole pulls in PyTorch. Keeping it out of the API image means the FastAPI server
stays a few MB and boots instantly, while the heavy training deps live in their own
environment — mirroring how a real team splits **online serving** from **offline
training**.

## Run it

```bash
# fresh Python 3.10 / 3.11 env recommended (RecBole pins older deps)
pip install -r requirements.txt

# 1) Benchmark on MovieLens-100k (auto-downloaded by RecBole)
python run_benchmark.py

# 2) …or on real PocketTaste signals from Mongo
python export_pockettaste.py            # events -> dataset/pockettaste/pockettaste.inter
python run_benchmark.py --dataset pockettaste
```

## What it shows

A leave-one-out, temporal-order evaluation (predict the *next* item) comparing:

| Model | Type | Role in PocketTaste |
|-------|------|---------------------|
| `Pop` | popularity baseline | the naive "trending" fallback we must beat |
| `GRU4Rec` | RNN session model | sequence-aware candidate generation |
| `SASRec` | self-attention | SOTA next-item; our target Stage-1 model |

Expected takeaway: **SASRec/GRU4Rec beat popularity on Recall@10 / NDCG@10** — the
quantitative case that session-aware ranking lifts "next series" prediction, which
is exactly what drives episode completion and coin unlocks.

## How this maps to the live engine

`../server` implements the full 3-stage architecture (candidate → rank → LLM
re-rank) in an explainable, hackathon-runnable form. In production you swap:

- **Stage 1 (candidates)** → the SASRec model benchmarked here, trained via RecBole,
  served with **NVIDIA Merlin** (NVTabular features + GPU inference).
- **Stage 2 (ranking)** → our transparent feature scorer → a Merlin DLRM / deep CTR
  model trained on completion + coin-unlock labels.
- **Stage 3 (conversational)** → the OpenAI layer → a **Haystack** retrieval pipeline.
