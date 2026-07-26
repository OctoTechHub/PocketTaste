"""Give every catalogue story real narrated audio, via Sarvam Bulbul.

The `stories` collection carries no audio: it has `episodes` as a *count*, no media
URL field, and the twelve `.claude` video files are Widevine-encrypted. So the
frontend had nothing real to play and fell back to stock music tracks joined by
content id, which is worse than silence — it sounds like the product works when the
audio has nothing to do with the story.

This narrates the actual text of each story in its own language and stores the WAV on
the item, so `/catalog/{id}/audio` serves something that genuinely belongs to it.

    python -m scripts.narrate_catalog --dry-run     # show what would be narrated
    python -m scripts.narrate_catalog               # narrate everything missing
    python -m scripts.narrate_catalog --force       # re-narrate, including existing
    python -m scripts.narrate_catalog --limit 5     # try a handful first
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.container import build_container
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.data.mongo import MongoGateway

logger = get_logger("narrate")

#: Placeholder rows from the DRM video ingest. They have no story text to read.
_SKIP_TITLE = "protected audio"


def _narration_text(item) -> str:
    """Title then description. The transcript is the same text on this catalogue, and
    reading it twice would double the cost for no benefit."""
    body = (item.description or "").strip()
    return f"{item.title}. {body}" if body else item.title


async def main(args: argparse.Namespace) -> int:
    configure_logging()
    settings = get_settings()
    gateway = MongoGateway(settings)
    if not await gateway.connect():
        logger.error("No MongoDB connection.")
        return 1
    container = build_container(settings, gateway)

    if not container.sarvam_finishing.available:
        logger.error("Sarvam is not configured — set SARVAM_API_KEY.")
        return 1

    items = [
        item
        for item in await container.content_repo.iter_all(with_transcript=False)
        if _SKIP_TITLE not in item.title.lower()
    ]
    pending = [item for item in items if args.force or not item.has_audio]
    if args.limit:
        pending = pending[: args.limit]

    logger.info(
        "%d catalogue stories, %d already narrated, %d to do",
        len(items),
        sum(1 for item in items if item.has_audio),
        len(pending),
    )
    if args.dry_run:
        for item in pending[:20]:
            logger.info("  would narrate %-28s %-9s %s", item.content_id, item.language, item.title[:40])
        return 0

    done = failed = 0
    total_kb = 0
    for index, item in enumerate(pending, start=1):
        result = await container.sarvam_finishing.narrate(
            _narration_text(item), language=item.language
        )
        audio = result.get("audio_base64")
        if not audio:
            failed += 1
            logger.warning("  [%d/%d] %-28s FAILED %s", index, len(pending), item.content_id, result.get("reason"))
            continue

        kilobytes = int(len(audio) * 0.75 / 1024)
        total_kb += kilobytes
        await container.content_repo.collection.update_one(
            {"content_id": item.content_id},
            {
                "$set": {
                    "audio_base64": audio,
                    "has_audio": True,
                    "audio_language": item.language,
                    "audio_source": "sarvam_tts",
                }
            },
        )
        done += 1
        if index % 10 == 0 or index == len(pending):
            logger.info("  [%d/%d] %d ok, %d failed, %d MB stored", index, len(pending), done, failed, total_kb // 1024)

    logger.info("Narrated %d stories (%d failed), %d MB of audio.", done, failed, total_kb // 1024)
    container.cache.invalidate()
    await container.aclose()
    await gateway.close()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="List what would be narrated.")
    parser.add_argument("--force", action="store_true", help="Re-narrate items that already have audio.")
    parser.add_argument("--limit", type=int, default=0, help="Only do the first N.")
    raise SystemExit(asyncio.run(main(parser.parse_args())))
