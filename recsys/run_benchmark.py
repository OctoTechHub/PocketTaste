"""RecBole offline benchmark for PocketTaste.

Trains a popularity baseline against two sequence-aware recommenders (GRU4Rec,
SASRec) with an identical leave-one-out, temporal-order evaluation and prints a
comparison table. This is the "we benchmarked SOTA sequence models" artifact — it
demonstrates the exact model family that powers PocketTaste's Stage-1 candidate
generation in production.

References: RecBole 2.0 (arXiv:2302.03561), SASRec (Kang & McAuley, 2018).

Usage (in a fresh Python 3.10/3.11 env):
    pip install -r requirements.txt
    python run_benchmark.py                  # MovieLens-100k (auto-downloaded)
    python run_benchmark.py --dataset pockettaste   # your exported data

`Recall@10 / NDCG@10` for the sequential models should clearly beat popularity —
the evidence that session-aware ranking lifts "next series" prediction.
"""
from __future__ import annotations

import argparse

from recbole.quick_start import run_recbole

MODELS = ["Pop", "GRU4Rec", "SASRec"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="ml-100k", help="ml-100k or pockettaste")
    parser.add_argument("--models", nargs="*", default=MODELS)
    args = parser.parse_args()

    rows: list[tuple[str, dict]] = []
    for model in args.models:
        print(f"\n=== Training {model} on {args.dataset} ===")
        result = run_recbole(
            model=model,
            dataset=args.dataset,
            config_file_list=["config.yaml"],
        )
        rows.append((model, result["test_result"]))

    print("\n" + "=" * 62)
    print(f"{'Model':<12}{'Recall@10':>13}{'NDCG@10':>13}{'MRR@10':>13}")
    print("-" * 62)
    for model, res in rows:
        recall = res.get("recall@10", 0.0)
        ndcg = res.get("ndcg@10", 0.0)
        mrr = res.get("mrr@10", 0.0)
        print(f"{model:<12}{recall:>13.4f}{ndcg:>13.4f}{mrr:>13.4f}")
    print("=" * 62)
    print("Sequence-aware models (SASRec/GRU4Rec) vs. Pop baseline — the lift is")
    print("the case for session-aware candidate generation in PocketTaste.")


if __name__ == "__main__":
    main()
