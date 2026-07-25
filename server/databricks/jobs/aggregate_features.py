"""Recompute behavioural features and listener profiles over the full event log.

The same deterministic code the API runs, on a cluster that can hold the whole log.
"""

from __future__ import annotations

from _common import build_context, get_spark, parse_args, run_async, write_delta


async def main() -> int:
    args = parse_args("Aggregate behavioural features.")
    _settings, gateway, container = await build_context()
    try:
        from app.agents.base import AgentOptions
        from app.domain.enums import AgentName

        run = await container.orchestrator.run(AgentOptions(use_llm=False), [AgentName.INGESTION])
        stage = run.stages[0]
        print(
            f"[aggregate_features] {stage.status.value} "
            f"processed={stage.processed} written={stage.written}"
        )
        for key, value in stage.stats.items():
            print(f"    {key}: {value}")

        features = await container.features_repo.list_all()
        write_delta(
            get_spark(),
            args.catalog,
            "content_features",
            [
                {
                    "content_id": row.content_id,
                    "plays": row.plays,
                    "unique_listeners": row.unique_listeners,
                    "completion_rate": row.completion_rate,
                    "drop_off_rate": row.drop_off_rate,
                    "quality_score": row.quality_score,
                    "confidence": row.confidence.value,
                    "provenance": row.provenance.value,
                    "computed_at": row.computed_at,
                }
                for row in features
            ],
        )
        return 1 if stage.status.value == "failed" else 0
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
