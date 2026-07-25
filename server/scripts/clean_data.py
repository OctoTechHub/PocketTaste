"""Strip the database back to real data only.

    python -m scripts.clean_data --dry-run    # show what would go (default)
    python -m scripts.clean_data --apply      # actually delete

What survives is exactly: the platform's own `stories` collection, the catalog
imported from it, content profiles, the registered accounts, and the activity those
accounts really generated.

The rule used to decide each collection is *provenance of the inputs*, not whether a
row looks tidy:

  KEEP    content_profiles  — embeddings and labels derived from the catalog text
                              alone. No event data feeds them, so no simulated
                              activity can have contaminated them.
  KEEP    user_profiles for real accounts — `build_user_profile` reads only that
                              user's own events, so a real account's profile cannot
                              contain another listener's behaviour.
  DELETE  content_features  — computed per item across *all* events for that item,
                              so every row mixes real and simulated listening.
  DELETE  creator_insights  — demand aggregates over the whole event log.
  DELETE  pipeline_runs / similarity_reports — history of runs against data that no
                              longer exists.

Nothing here ever writes to the upstream `stories` collection.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.container import build_container  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.data.mongo import MongoGateway  # noqa: E402
from app.services.auth_service import ACCOUNT_PREFIX  # noqa: E402

logger = get_logger("clean")


async def snapshot(container, settings) -> dict:
    activity = container.activity_repo.collection
    accounts = [account.user_id for account in await container.accounts_repo.list_accounts(limit=1000)]
    return {
        f"{settings.stories_collection} (upstream, read-only)": await container.gateway.database[
            settings.stories_collection
        ].count_documents({}),
        "content_items": await container.content_repo.count(),
        "content_items (synthetic)": await container.content_repo.count({"is_synthetic": True}),
        "content_profiles": await container.profile_repo.count(),
        "content_features": await container.features_repo.count(),
        "activity_events": await activity.count_documents({}),
        "activity_events (simulated)": await activity.count_documents({"is_synthetic": True}),
        "activity_events (real, by an account)": await activity.count_documents(
            {"is_synthetic": False, "user_id": {"$in": accounts}}
        ),
        "activity_events (real, orphaned)": await activity.count_documents(
            {"is_synthetic": False, "user_id": {"$nin": accounts}}
        ),
        "user_profiles": await container.users_repo.count(),
        "user_accounts": len(accounts),
        "creator_insights": await container.insight_repo.collection.count_documents({}),
        "similarity_reports": await container.similarity_audit_repo.collection.count_documents({}),
        "pipeline_runs": await container.runs_repo.count(),
    }


async def main(args: argparse.Namespace) -> int:
    configure_logging()
    settings = get_settings()
    gateway = MongoGateway(settings)

    if not await gateway.connect():
        logger.error("Cannot connect to MongoDB. Set DB_URL in server/.env.")
        return 1

    container = build_container(settings, gateway)
    try:
        accounts = await container.accounts_repo.list_accounts(limit=1000)
        account_ids = [account.user_id for account in accounts]
        if not account_ids:
            logger.error(
                "No registered accounts. Run scripts/onboard_users.py first, otherwise this "
                "would delete every event and leave nothing behind."
            )
            return 1

        logger.info("Real accounts kept (%d):", len(accounts))
        for account in accounts:
            logger.info("    %-24s %s", account.email, account.user_id)

        logger.info("")
        logger.info("BEFORE:")
        for key, value in (await snapshot(container, settings)).items():
            logger.info("    %-42s %d", key, value)

        activity = container.activity_repo.collection
        # Real events not tied to a live account are leftovers from probes. They are
        # not simulated, but they are not attributable either, so they go too.
        plan = [
            ("simulated activity events", activity, {"is_synthetic": True}),
            (
                "orphaned real events (no live account)",
                activity,
                {"is_synthetic": False, "user_id": {"$nin": account_ids}},
            ),
            ("synthetic catalog items", container.content_repo.collection, {"is_synthetic": True}),
            (
                "user profiles not belonging to an account",
                container.users_repo.collection,
                {"user_id": {"$nin": account_ids}},
            ),
            (
                "content features (computed across simulated events)",
                container.features_repo.collection,
                {},
            ),
            ("creator insight reports (aggregated over simulated events)",
             container.insight_repo.collection, {}),
            ("similarity audit records", container.similarity_audit_repo.collection, {}),
            ("pipeline run history", container.runs_repo.collection, {}),
        ]

        logger.info("")
        logger.info("PLAN (%s):", "APPLY" if args.apply else "DRY RUN")
        total = 0
        for label, collection, query in plan:
            count = await collection.count_documents(query)
            total += count
            logger.info("    %-58s %d", f"delete {label}", count)

        if not args.apply:
            logger.info("")
            logger.info("Nothing was deleted. Re-run with --apply to remove these %d documents.", total)
            return 0

        logger.info("")
        for label, collection, query in plan:
            result = await collection.delete_many(query)
            logger.info("    deleted %-50s %d", label, result.deleted_count)

        # Also drop synthetic catalog items' profiles, which would now be orphans.
        live_ids = [item.content_id for item in await container.content_repo.iter_all(with_transcript=False)]
        orphaned = await container.profile_repo.collection.delete_many(
            {"content_id": {"$nin": live_ids}}
        )
        if orphaned.deleted_count:
            logger.info("    deleted %-50s %d", "orphaned content profiles", orphaned.deleted_count)

        logger.info("")
        logger.info("AFTER:")
        for key, value in (await snapshot(container, settings)).items():
            logger.info("    %-42s %d", key, value)

        logger.info("")
        logger.info("Data is now real-only. The pipeline was NOT run.")
        logger.info("When you want derived state rebuilt from this real activity:")
        logger.info("    python -m scripts.seed --no-pipeline   # (nothing to load; catalog is present)")
        logger.info("    POST /pipeline/run                     # or run the agents directly")
        return 0
    finally:
        await gateway.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reduce the database to real data only.")
    parser.add_argument("--apply", action="store_true", help="Perform the deletions.")
    parser.add_argument("--dry-run", action="store_true", help="Show the plan only (default).")
    raise SystemExit(asyncio.run(main(parser.parse_args())))
