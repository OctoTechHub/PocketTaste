"""Print the content-demand report: which genres need more content, and why.

    python -m scripts.demand_report              # use the stored report
    python -m scripts.demand_report --refresh    # recompute from the current event log
    python -m scripts.demand_report --top 10
    python -m scripts.demand_report --preview-at-scale   # what it looks like with real traffic

This is the creator-facing answer the whole pipeline exists to produce: *these
genres have demand the catalog is not serving*. Every number printed is computed
from logged behaviour — nothing here is estimated, and the provenance line at the
top says exactly what kind of data produced it.
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
from app.domain.enums import EventType  # noqa: E402

logger = get_logger("demand")

WIDTH = 84
BAR = 26


def rule(char: str = "=") -> str:
    return char * WIDTH


def bar(share: float, scale: float) -> str:
    """Render a share as a bar, scaled against the largest value on screen."""
    filled = int(round((share / scale) * BAR)) if scale > 0 else 0
    return "#" * max(0, min(BAR, filled)) + "." * (BAR - max(0, min(BAR, filled)))


def verdict(row) -> str:
    if not row.supply_share:
        return "NOTHING IN THE CATALOG FOR THIS"
    ratio = row.demand_share / row.supply_share
    if ratio >= 2.0:
        return f"NEEDS MUCH MORE CONTENT ({ratio:.1f}x demand vs supply)"
    if ratio >= 1.15:
        return f"NEEDS MORE CONTENT ({ratio:.1f}x demand vs supply)"
    return "adequately supplied"


async def main(args: argparse.Namespace) -> int:
    configure_logging()
    settings = get_settings()
    gateway = MongoGateway(settings)
    if not await gateway.connect():
        logger.error("Cannot connect to MongoDB. Set DB_URL in server/.env.")
        return 1

    container = build_container(settings, gateway)
    try:
        if args.preview_at_scale:
            return await _preview_at_scale(container, top=args.top)

        report = None if args.refresh else await container.insight_repo.latest()

        if report is None:
            catalog = await container.content_repo.iter_all(with_transcript=False)
            features = await container.features_repo.all_by_id()
            if not catalog:
                logger.error("Catalog is empty. Run scripts/seed.py first.")
                return 1
            if not features:
                logger.error(
                    "No behavioural features yet, so demand cannot be measured. "
                    "Run POST /pipeline/run (or scripts/seed.py) first."
                )
                return 1
            events = await container.activity_repo.stream_all()
            profiles = await container.profile_repo.all_by_id()
            report = await container.demand.build_report(
                catalog, events, features, profiles, use_llm=container.llm.available
            )
            await container.insight_repo.save(report)

        events = await container.activity_repo.stream_all()
        searches = [
            event
            for event in events
            if event.event_type is EventType.SEARCH and event.result_count == 0 and event.query
        ]
        _render(report, searches, top=args.top)
        return 0
    finally:
        await gateway.close()


async def _preview_at_scale(container, *, top: int) -> int:
    """Show the report as it would read with a full listening population.

    Entirely in memory: the simulated events are never written, so the database keeps
    exactly the real activity it already has. This exists because with a handful of
    real listeners every row is honestly labelled `confidence: LOW`, which tells you
    nothing about whether the analysis itself works.
    """
    from app.services.catalog_simulation import RealCatalogSimulator
    from app.services.feature_builder import build_content_features

    catalog = await container.content_repo.iter_all(with_transcript=False)
    if not catalog:
        logger.error("Catalog is empty. Run scripts/seed.py first.")
        return 1

    logger.info("Simulating a listening population over the real catalog (nothing is saved)...")
    simulated = RealCatalogSimulator(user_count=400).run(catalog).events
    by_content: dict[str, list] = {}
    for event in simulated:
        if event.content_id:
            by_content.setdefault(event.content_id, []).append(event)

    features = {
        item.content_id: build_content_features(
            item,
            by_content.get(item.content_id, []),
            min_confident_sample_size=container.settings.min_confident_sample_size,
        )
        for item in catalog
    }
    profiles = await container.profile_repo.all_by_id()
    report = await container.demand.build_report(
        catalog, simulated, features, profiles, use_llm=container.llm.available
    )

    print()
    print(rule("*"))
    print("  PREVIEW ONLY - simulated listening over the real catalog.")
    print("  Nothing was written to the database; your real activity is untouched.")
    print(rule("*"))
    _render(report, [e for e in simulated if e.event_type is EventType.SEARCH and e.result_count == 0],
            top=top)
    return 0


def _render(report, unmet_searches, *, top: int) -> None:
    print()
    print(rule())
    print("  CONTENT DEMAND REPORT".ljust(WIDTH))
    print(
        f"  {report.catalog_items} stories  |  {report.events_analysed} events  |  "
        f"{report.unique_listeners} listeners  |  generated {report.generated_at:%Y-%m-%d %H:%M} UTC"
    )
    print(f"  data: {report.provenance.value}")
    print(rule())

    under = [row for row in report.segments if row.opportunity_score > 0][:top]
    over = [row for row in report.segments if row.opportunity_score <= 0]

    # ---- the headline ----------------------------------------------------
    print()
    print("  GENRES THAT NEED MORE CONTENT")
    print("  " + rule("-")[:WIDTH - 2])
    if not under:
        print("    Nothing is under-served on the current data.")
    else:
        scale = max(max(r.demand_share for r in under), max(r.supply_share for r in under))
        for rank, row in enumerate(under, start=1):
            print()
            print(f"  #{rank}  {row.segment.upper()}       -> {verdict(row)}")
            print(f"        listeners want   {bar(row.demand_share, scale)}  {row.demand_share:6.1%}")
            print(f"        catalog offers   {bar(row.supply_share, scale)}  {row.supply_share:6.1%}")
            evidence = [
                f"{row.catalog_items} stories",
                f"{row.unique_listeners} listeners",
                f"{row.plays} plays",
                f"{row.completions} completions",
            ]
            if row.unmet_search_count:
                evidence.append(f"{row.unmet_search_count} searches returned NOTHING")
            print(f"        evidence: {' | '.join(evidence)}")
            print(
                f"        gap {row.opportunity_score:+.4f}  "
                f"completion {row.completion_rate:.0%}  drop-off {row.drop_off_rate:.0%}  "
                f"confidence {row.confidence.value.upper()} (n={row.sample_size})"
            )

    # ---- audience is there, content is losing them -----------------------
    execution = sorted(
        (row for row in report.segments if row.execution_gap > 0 and row.drop_off_rate > 0.4),
        key=lambda row: row.execution_gap,
        reverse=True,
    )[:3]
    if execution:
        print()
        print("  AUDIENCE IS THERE, BUT THE CONTENT IS LOSING THEM")
        print("  " + rule("-")[:WIDTH - 2])
        for row in execution:
            print(
                f"    {row.segment:28} drop-off {row.drop_off_rate:5.0%}  "
                f"completion {row.completion_rate:5.0%}  ({row.unique_listeners} listeners)"
            )
        print("    -> the demand is proven; better execution beats more volume here.")

    # ---- what listeners asked for and did not get ------------------------
    if unmet_searches:
        from collections import Counter

        counts = Counter(event.query for event in unmet_searches)
        print()
        print("  SEARCHES THAT RETURNED NOTHING")
        print("  " + rule("-")[:WIDTH - 2])
        for query, count in counts.most_common(6):
            print(f"    {count:4}x  {query}")
        if report.unattributed_unmet_searches:
            print(
                f"    ({report.unattributed_unmet_searches} more could not be tied to a "
                "genre/language cell and were left out rather than guessed)"
            )

    # ---- over-supplied ---------------------------------------------------
    if over:
        print()
        print("  ALREADY WELL SUPPLIED")
        print("  " + rule("-")[:WIDTH - 2])
        for row in sorted(over, key=lambda r: r.supply_share, reverse=True)[:5]:
            print(
                f"    {row.segment:28} {row.catalog_items:3} stories  "
                f"supply {row.supply_share:5.1%}  demand {row.demand_share:5.1%}"
            )

    saturated = [row for row in report.saturated_patterns if row.saturation_index > 1.0][:4]
    if saturated:
        print()
        print("  OVER-USED STORY PATTERNS (lots of catalog, weak retention)")
        print("  " + rule("-")[:WIDTH - 2])
        for row in saturated:
            print(
                f"    {row.narrative_pattern:30} {row.share_of_catalog:5.1%} of catalog  "
                f"completion {row.avg_completion_rate:5.0%}  index {row.saturation_index:.2f}  "
                f"({row.measured_items} measured, {row.listeners} listeners)"
            )

    # ---- briefs ----------------------------------------------------------
    if report.briefs:
        print()
        print("  WHAT TO WRITE NEXT")
        print("  " + rule("-")[:WIDTH - 2])
        for index, brief in enumerate(report.briefs[:top], start=1):
            print(f"    {index}. {brief.headline}")
            for line in _wrap(brief.rationale, WIDTH - 8):
                print(f"       {line}")
            if brief.avoid_patterns:
                print(f"       avoid: {', '.join(brief.avoid_patterns)}")
            print(f"       [{brief.confidence.value} confidence, written by {brief.generated_by.value}]")

    print()
    print(rule())
    for line in _wrap(report.data_notice, WIDTH - 4):
        print(f"  {line}")
    print(rule())
    print()


def _wrap(text: str, width: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Print the content-demand report.")
    parser.add_argument("--refresh", action="store_true", help="Recompute instead of using the stored report.")
    parser.add_argument("--top", type=int, default=6, help="How many segments to show.")
    parser.add_argument(
        "--preview-at-scale",
        action="store_true",
        help="Simulate a full listening population in memory to show the report at strength. "
        "Writes nothing to the database.",
    )
    raise SystemExit(asyncio.run(main(parser.parse_args())))
