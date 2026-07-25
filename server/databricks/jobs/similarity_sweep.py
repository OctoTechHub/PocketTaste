"""All-pairs duplicate sweep across the whole catalog.

The online gate compares an upload against a retrieved shortlist — the right trade
for one upload, the wrong one for auditing everything. This is the O(n^2) pass that
shortlist retrieval exists to avoid during a request.
"""

from __future__ import annotations

from _common import build_context, get_spark, parse_args, run_async, write_delta


async def main() -> int:
    args = parse_args("Sweep the catalog for duplicates.")
    _settings, gateway, container = await build_context()
    try:
        from app.domain.enums import DuplicateKind

        catalog = await container.content_repo.iter_all(with_transcript=True)
        profiles = await container.profile_repo.all_by_id()
        if not catalog or not profiles:
            print("[similarity_sweep] nothing to sweep")
            return 0

        findings = []
        for item in catalog:
            profile = profiles.get(item.content_id)
            if profile is None:
                continue
            matches = container.similarity.compare_all(
                item, profile, catalog, profiles, exclude_content_id=item.content_id
            )
            matches.sort(key=lambda match: match.combined_score, reverse=True)
            container.intelligence.apply_originality(
                profile,
                [
                    (match.content_id, match.title, match.combined_score, match.duplicate_kind)
                    for match in matches
                ],
            )
            if profile.duplicate_kind is not DuplicateKind.NONE and matches:
                top = matches[0]
                findings.append(
                    {
                        "content_id": item.content_id,
                        "title": item.title,
                        "creator_id": item.creator_id,
                        "duplicate_kind": profile.duplicate_kind.value,
                        "duplicate_risk": profile.duplicate_risk,
                        "matches_content_id": top.content_id,
                        "matches_title": top.title,
                        "combined_score": top.combined_score,
                    }
                )

        await container.profile_repo.upsert_many(list(profiles.values()))
        print(f"[similarity_sweep] compared {len(catalog)} items pairwise; {len(findings)} flagged")
        for row in findings[:20]:
            print(
                f"    {row['duplicate_kind']:18} {row['title'][:38]:38} ~ {row['matches_title'][:34]}"
            )

        write_delta(get_spark(), args.catalog, "duplicate_findings", findings)
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
