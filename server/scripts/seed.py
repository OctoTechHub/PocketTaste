"""Load a catalog into MongoDB and run the agent pipeline over it.

Two sources:

    python -m scripts.seed --source stories --reset    # the platform's real catalog
    python -m scripts.seed --source synthetic --reset  # the built-in simulator

`stories` is the default. It imports the real `Click.stories` collection (read-only)
and reconstructs an event log calibrated to each story's real plays, likes and
rating — because the catalog records aggregate totals but no per-listener events,
and the feature builder needs events.

Flags:
    --reset             wipe the derived collections first
    --purge-simulated   drop every simulated event and rebuild on real activity only
    --no-pipeline       load only
    --no-llm            heuristic labels, zero API spend
    --users N           simulated listener count
    --seed N            RNG seed (the run is fully reproducible)

Nothing here ever writes to the upstream `stories` collection.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.base import AgentOptions  # noqa: E402
from app.container import build_container  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.data.mongo import MongoGateway  # noqa: E402
from app.data.stories_source import StoriesSource  # noqa: E402
from app.services.catalog_simulation import RealCatalogSimulator  # noqa: E402
from app.services.simulation import BehaviourSimulator  # noqa: E402

logger = get_logger("seed")


async def main(args: argparse.Namespace) -> int:
    configure_logging()
    settings = get_settings()
    gateway = MongoGateway(settings)

    if not await gateway.connect():
        logger.error("Cannot connect to MongoDB. Set DB_URL in server/.env.")
        return 1

    container = build_container(settings, gateway)
    try:
        if args.purge_simulated:
            # Cut over to real-only once enough authenticated traffic exists. Accounts,
            # the catalog and real events are untouched.
            removed = await container.activity_repo.collection.delete_many({"is_synthetic": True})
            await container.users_repo.collection.delete_many({"user_id": {"$regex": "^listener_"}})
            logger.info("Purged %d simulated events and their listener profiles.", removed.deleted_count)
            run = await container.orchestrator.run(
                AgentOptions(use_llm=False),
                container.orchestrator.resolve_stages(["ingestion_agent", "insight_agent"]),
            )
            logger.info("Rebuilt features on real-only data: %s", run.status.value)
            remaining = await container.activity_repo.count()
            logger.info("Remaining events (all real): %d", remaining)
            if remaining < 200:
                logger.warning(
                    "Only %d real events remain. Demand and evaluation output will be thin "
                    "until more listening is logged.",
                    remaining,
                )
            return 0

        if args.reset:
            logger.info("Resetting derived collections (upstream 'stories' is untouched)...")
            for repo in (
                container.content_repo,
                container.activity_repo,
                container.profile_repo,
                container.features_repo,
                container.users_repo,
                container.runs_repo,
            ):
                deleted = await repo.delete_all()
                logger.info("  cleared %-18s (%d docs)", repo.collection_name, deleted)
            await container.insight_repo.collection.delete_many({})
            await container.similarity_audit_repo.collection.delete_many({})

        existing = await container.content_repo.count()
        if existing and not args.reset:
            logger.warning("Catalog already holds %d items. Use --reset to rebuild.", existing)
        elif args.source == "stories":
            if not await _load_real_stories(container, settings, args):
                return 1
        else:
            await _load_synthetic(container, args)

        if args.pipeline:
            logger.info("Running the agent pipeline (llm=%s)...", args.llm and container.llm.available)
            run = await container.orchestrator.run(
                AgentOptions(use_llm=args.llm and container.llm.available, force_relabel=args.reset)
            )
            logger.info("Pipeline %s: %s in %dms", run.run_id, run.status.value, run.duration_ms)
            for stage in run.stages:
                logger.info(
                    "  %-28s %-9s %6dms  processed=%-6d written=%-6d %s",
                    stage.agent,
                    stage.status.value,
                    stage.duration_ms,
                    stage.processed,
                    stage.written,
                    stage.error or "",
                )
                for key, value in stage.stats.items():
                    logger.info("      %-24s %s", key, value)
        return 0
    finally:
        await gateway.close()


async def _load_real_stories(container, settings, args) -> bool:
    source = StoriesSource(container.gateway, settings)
    if not await source.available():
        logger.error(
            "Collection '%s' not found in database '%s'. Use --source synthetic instead.",
            settings.stories_collection,
            settings.mongo_db_name,
        )
        return False

    logger.info("Importing real catalog from %s.%s ...", settings.mongo_db_name, settings.stories_collection)
    catalog = await source.load()
    if not catalog:
        logger.error("Upstream collection is empty.")
        return False

    await container.content_repo.upsert_many(catalog)
    for key, value in StoriesSource.summarise(catalog).items():
        logger.info("  %-18s %s", key, value)

    logger.info("Simulating a listener event log calibrated to real plays/likes/rating...")
    result = RealCatalogSimulator(seed=args.seed, user_count=args.users).run(catalog)
    for start in range(0, len(result.events), 2000):
        await container.activity_repo.insert_many(result.events[start : start + 2000])
    for key, value in result.notes.items():
        logger.info("  %-22s %s", key, value)
    return True


async def _load_synthetic(container, args) -> None:
    logger.info("Simulating a synthetic catalog (seed=%d, users=%d)...", args.seed, args.users)
    result = BehaviourSimulator(seed=args.seed, user_count=args.users).run()
    await container.content_repo.upsert_many(result.catalog)
    logger.info("Wrote %d catalog items", len(result.catalog))
    for start in range(0, len(result.events), 2000):
        await container.activity_repo.insert_many(result.events[start : start + 2000])
    logger.info("Wrote %d activity events", len(result.events))
    for key, value in result.notes.items():
        logger.info("  %-28s %s", key, value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load a catalog and run the PocketTaste pipeline.")
    parser.add_argument(
        "--source",
        choices=("stories", "synthetic"),
        default="stories",
        help="'stories' imports the platform's real catalog; 'synthetic' generates one.",
    )
    parser.add_argument("--reset", action="store_true", help="Wipe derived collections first.")
    parser.add_argument(
        "--purge-simulated",
        action="store_true",
        help="Delete all simulated events and rebuild on real authenticated activity only.",
    )
    parser.add_argument("--users", type=int, default=400, help="Number of simulated listeners.")
    parser.add_argument("--seed", type=int, default=20260725, help="RNG seed for reproducibility.")
    parser.add_argument("--no-pipeline", dest="pipeline", action="store_false", help="Load only.")
    parser.add_argument("--no-llm", dest="llm", action="store_false", help="Heuristic labels only.")
    parser.set_defaults(pipeline=True, llm=True)
    raise SystemExit(asyncio.run(main(parser.parse_args())))
