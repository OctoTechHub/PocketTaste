"""Nightly offline evaluation, appended to Delta so accuracy is tracked over time.

A single Recall@K is a number. A history of them is a regression test — you find out
that a weight change cost you 4 points before a creator does.
"""

from __future__ import annotations

from _common import build_context, get_spark, parse_args, run_async, write_delta


async def main() -> int:
    args = parse_args("Evaluate the ranker offline.")
    _settings, gateway, container = await build_context()
    try:
        catalog = await container.content_repo.iter_all(with_transcript=False)
        events = await container.activity_repo.stream_all()
        profiles = await container.profile_repo.all_by_id()

        report = container.evaluation.evaluate(catalog, events, profiles, k=10, max_users=5000)
        payload = report.as_dict()

        print(f"[evaluate_ranker] users={payload['users_evaluated']} split={payload['split_at']}")
        for row in payload["results"]:
            print(
                f"    {row['strategy']:22} recall={row['recall_at_k']:.4f} "
                f"ndcg={row['ndcg_at_k']:.4f} mrr={row['mrr']:.4f} "
                f"coverage={row['catalog_coverage']:.3f}"
            )
        for caveat in payload["caveats"]:
            print(f"    caveat: {caveat}")

        # Append, never overwrite: the point of running this nightly is the trend.
        write_delta(
            get_spark(),
            args.catalog,
            "evaluation_runs",
            [
                {
                    **row,
                    "k": payload["k"],
                    "generated_at": payload["generated_at"],
                    "provenance": payload["provenance"],
                }
                for row in payload["results"]
            ],
            mode="append",
        )
        return 0
    finally:
        await gateway.close()


if __name__ == "__main__":
    # Deliberately not `raise SystemExit(...)`. Databricks executes the task inside an
    # IPython kernel, where SystemExit — even SystemExit(0) — is surfaced as a task
    # failure. Return normally on success; raise a real error on failure.
    _exit_code = run_async(main())
    if _exit_code:
        raise RuntimeError(f"task failed with exit code {_exit_code}")
    print("task completed successfully")
