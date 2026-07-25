"""Re-embed and re-label catalog items whose profile is missing or stale.

The only task that spends API credits — which is exactly why it lives here on a
nightly schedule rather than inside the API's background loop.
"""

from __future__ import annotations

from _common import build_context, get_spark, parse_args, run_async, write_delta


async def main() -> int:
    args = parse_args("Refresh content embeddings and labels.")
    _settings, gateway, container = await build_context()
    try:
        from app.agents.base import AgentOptions
        from app.domain.enums import AgentName

        run = await container.orchestrator.run(
            AgentOptions(use_llm=not args.dry_run, force_relabel=False),
            [AgentName.CONTENT_INTELLIGENCE],
        )
        stage = run.stages[0]
        print(
            f"[refresh_embeddings] {stage.status.value} "
            f"processed={stage.processed} written={stage.written}"
        )
        for key, value in stage.stats.items():
            print(f"    {key}: {value}")

        profiles = await container.profile_repo.list_all()
        write_delta(
            get_spark(),
            args.catalog,
            "content_profiles",
            [
                {
                    "content_id": profile.content_id,
                    "embedding_model": profile.embedding_model,
                    "dimensions": profile.embedding_dimensions,
                    "narrative_pattern": profile.narrative_pattern,
                    "label_source": profile.label_source.value,
                    "computed_at": profile.computed_at,
                }
                for profile in profiles
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
