"""Full-catalog clustering on the narrative-arc embedding.

The API never does this during a request. Here every profile is reclustered in one
pass, because a single new item can merge two existing clusters and only a full pass
will notice.
"""

from __future__ import annotations

from collections import Counter

from _common import build_context, get_spark, parse_args, run_async, write_delta


async def main() -> int:
    args = parse_args("Recluster the catalog.")
    _settings, gateway, container = await build_context()
    try:
        profiles = await container.profile_repo.list_all()
        if not profiles:
            print("[rebuild_clusters] no profiles yet; run refresh_embeddings first")
            return 0

        clustered = container.intelligence.cluster(profiles)
        written = await container.profile_repo.upsert_many(list(clustered.values()))
        sizes = Counter(profile.cluster_id for profile in clustered.values())
        families = {cluster: count for cluster, count in sizes.items() if count > 1}

        print(
            f"[rebuild_clusters] {len(clustered)} profiles -> {len(sizes)} clusters, "
            f"{written} written"
        )
        print(f"[rebuild_clusters] {len(families)} clusters hold more than one story")

        write_delta(
            get_spark(),
            args.catalog,
            "content_clusters",
            [{"cluster_id": cluster, "size": count} for cluster, count in sizes.items()],
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
