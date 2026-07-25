"""Ingest real audio files into the catalog, with real transcripts.

    python -m scripts.ingest_audio --source ../../.claude              # dry run
    python -m scripts.ingest_audio --source ../../.claude --apply
    python -m scripts.ingest_audio --source ../../.claude --apply --screen

Until now the catalog held a synopsis, not a script, so content understanding was
metadata-deep. This closes that gap: Whisper transcribes the audio and the story
profile is built from what is actually said.

Four steps:

1. **Hash first.** Byte-identical files are detected before anything is spent, so a
   set of copies costs one transcription rather than five.
2. **Downmix.** Whisper caps uploads at 25 MB. A 21-minute 192 kbps stereo file is
   32 MB; at 16 kHz mono it is about 3 MB, and Whisper resamples to 16 kHz anyway,
   so nothing useful is lost.
3. **Transcribe, then label.** The transcript is real. Title, genre and language are
   derived from it by the LLM, not invented from the filename.
4. **Screen.** Every ingested item runs through the similarity gate, which is the
   point: identical audio under different filenames must be flagged.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.container import build_container  # noqa: E402
from app.core.clock import utcnow  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.data.mongo import MongoGateway  # noqa: E402
from app.domain.enums import ContentSource  # noqa: E402
from app.domain.models import Chapter, ContentItem  # noqa: E402
from app.services.similarity import SimilarityCandidate  # noqa: E402

logger = get_logger("audio")

AUDIO_SUFFIXES = {".mp4", ".m4a", ".mp3", ".wav", ".aac", ".ogg", ".flac", ".webm"}

#: Boxes that mark an MPEG Common Encryption stream. Their presence means the audio
#: samples are encrypted and no decoder can read them without the content key.
DRM_BOXES = (b"pssh", b"tenc", b"senc", b"enca")
#: Whisper rejects uploads above 25 MB. Stay clear of the edge.
MAX_UPLOAD_BYTES = 24 * 1024 * 1024
EPISODE_SECONDS = 420  # 7 minutes, the median episode length in this catalog

_LABEL_PROMPT = """Below is a transcript of an audio story episode. Describe it.

Transcript (first part):
{excerpt}

Return exactly this JSON:
{{
  "title": "a natural title for this story, 2-6 words, no quotes",
  "description": "2-3 sentences describing what happens",
  "genre": "one of: horror, thriller, romance, crime-detective, supernatural, mythology-fantasy, sci-fi, suspense, revenge-drama, comedy-slice-of-life",
  "language": "one of: hi, hinglish, en, ta, te, bn, mr",
  "tags": ["3-6 short tags"]
}}

Base every field on the transcript only. If the speech is Hindi written in Latin
script, the language is hinglish."""


@dataclass(slots=True)
class AudioFile:
    path: Path
    sha256: str
    size_bytes: int
    duration_seconds: float
    drm: bool = False
    transcript: str = ""
    labels: dict = field(default_factory=dict)


def is_drm_protected(path: Path) -> bool:
    """True when the container carries MPEG Common Encryption metadata.

    A DRM-protected file still reports its codec and duration through ffprobe, which
    makes it look ingestible right up until the decoder emits noise. Checking the
    container up front turns a wall of AAC errors into one clear message.

    We do not attempt to decrypt. That needs a licence-server content key, and
    stripping it is not something this tool does.
    """
    head = path.read_bytes()[: 2 * 1024 * 1024]
    return sum(box in head for box in DRM_BOXES) >= 2


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except Exception:  # noqa: BLE001
        return 0.0


def to_whisper_input(path: Path, workdir: Path) -> Path:
    """Downmix to 16 kHz mono MP3 so large files fit under the upload cap."""
    target = workdir / f"{path.stem}.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(path),
         "-ac", "1", "-ar", "16000", "-b:a", "32k", str(target)],
        check=True,
    )
    return target


def scan(source: Path) -> tuple[list[AudioFile], dict[str, list[Path]]]:
    """Return one entry per unique audio, plus the filenames that share each hash."""
    by_hash: dict[str, list[Path]] = {}
    for path in sorted(source.iterdir()):
        if path.suffix.lower() not in AUDIO_SUFFIXES or not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        by_hash.setdefault(digest, []).append(path)

    unique = [
        AudioFile(
            path=paths[0], sha256=digest, size_bytes=paths[0].stat().st_size,
            duration_seconds=probe_duration(paths[0]), drm=is_drm_protected(paths[0]),
        )
        for digest, paths in by_hash.items()
    ]
    unique.sort(key=lambda item: item.duration_seconds)
    return unique, by_hash


def episodes_for(duration: float) -> list[Chapter]:
    count = max(1, int(duration // EPISODE_SECONDS) or 1)
    length = int(duration / count)
    return [
        Chapter(index=i, title=f"Part {i + 1}",
                start_seconds=i * length, end_seconds=(i + 1) * length)
        for i in range(count)
    ]


async def transcribe(container, item: AudioFile, workdir: Path) -> str:
    from openai import AsyncOpenAI

    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_secret, timeout=600, max_retries=2)

    upload = item.path
    if item.size_bytes > MAX_UPLOAD_BYTES:
        upload = to_whisper_input(item.path, workdir)
        logger.info("    downmixed %.1f MB -> %.1f MB",
                    item.size_bytes / 1e6, upload.stat().st_size / 1e6)

    with upload.open("rb") as handle:
        result = await client.audio.transcriptions.create(
            model="whisper-1", file=handle, response_format="text"
        )
    return str(result).strip()


async def label(container, transcript: str) -> dict:
    result = await container.llm.complete_json(
        _LABEL_PROMPT.format(excerpt=transcript[:6000]), max_tokens=500, temperature=0.2
    )
    return result.data if result.ok else {}


async def main(args: argparse.Namespace) -> int:
    configure_logging()
    if not shutil.which("ffprobe"):
        logger.error("ffprobe is required. Install ffmpeg and retry.")
        return 1

    source = Path(args.source).resolve()
    if not source.is_dir():
        logger.error("Not a directory: %s", source)
        return 1

    unique, by_hash = scan(source)
    if not unique:
        logger.error("No audio files found in %s", source)
        return 1

    total_files = sum(len(paths) for paths in by_hash.values())
    total_minutes = sum(item.duration_seconds for item in unique) / 60

    logger.info("Source: %s", source)
    logger.info("%d files, %d unique by content hash", total_files, len(unique))
    logger.info("")
    for item in unique:
        copies = by_hash[item.sha256]
        marker = f"  <-- {len(copies)} copies" if len(copies) > 1 else ""
        lock = " [DRM]" if item.drm else ""
        logger.info("  %6.1f MB  %6.2f min  %s%s%s",
                    item.size_bytes / 1e6, item.duration_seconds / 60, copies[0].name, lock, marker)
    protected = [item for item in unique if item.drm]
    open_audio = [item for item in unique if not item.drm]
    open_minutes = sum(item.duration_seconds for item in open_audio) / 60

    logger.info("")
    duplicates = sum(len(p) - 1 for p in by_hash.values() if len(p) > 1)
    logger.info("Duplicate files detected by content hash: %d", duplicates)

    if protected:
        logger.info("")
        logger.info("%d of %d recordings are DRM-protected (MPEG Common Encryption).",
                    len(protected), len(unique))
        logger.info("Their audio samples are encrypted, so no decoder and no")
        logger.info("transcription service can read them. This tool does not strip DRM.")
        logger.info("They are still ingested: duration, episode layout and an audio")
        logger.info("fingerprint all work without decryption, and the fingerprint is")
        logger.info("what catches the same recording uploaded under another name.")

    if open_audio:
        logger.info("")
        logger.info("Transcribable: %.1f min, about $%.2f", open_minutes, open_minutes * 0.006)

    if not args.apply:
        logger.info("")
        logger.info("Dry run. Re-run with --apply to transcribe and ingest.")
        return 0

    settings = get_settings()
    if not settings.openai_secret:
        logger.error("OPENAI_KEY is required to transcribe.")
        return 1

    gateway = MongoGateway(settings)
    if not await gateway.connect():
        logger.error("Cannot reach MongoDB.")
        return 1
    container = build_container(settings, gateway)

    try:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            for index, item in enumerate(unique, start=1):
                if item.drm:
                    logger.info("[%d/%d] %s -- DRM protected, ingesting metadata only",
                                index, len(unique), item.path.name)
                    continue
                logger.info("[%d/%d] transcribing %s ...", index, len(unique), item.path.name)
                try:
                    item.transcript = await transcribe(container, item, workdir)
                    logger.info("    %d characters", len(item.transcript))
                    item.labels = await label(container, item.transcript)
                    logger.info("    -> %s | %s | %s",
                                item.labels.get("title"), item.labels.get("genre"),
                                item.labels.get("language"))
                except Exception as exc:  # noqa: BLE001 - one bad file must not stop the run
                    logger.error("    transcription failed: %s", str(exc)[:160])

        # One catalog entry per FILE, not per unique audio. The copies are the point:
        # the gate has to notice that they are the same story under different names.
        stories = container.gateway.database[settings.stories_collection]
        created: list[ContentItem] = []
        for item in unique:
            for copy_index, path in enumerate(by_hash[item.sha256]):
                base = item.labels.get("title") or path.stem.replace("_", " ").strip()
                title = base if copy_index == 0 else f"{base} ({copy_index + 1})"
                slug = "audio-" + hashlib.sha1(
                    f"{item.sha256}{copy_index}".encode()
                ).hexdigest()[:12]

                content = ContentItem(
                    content_id=slug,
                    title=title,
                    description=item.labels.get("description", "")[:2000] or title,
                    # Real transcript when we could read the audio, otherwise empty --
                    # never a placeholder that could be mistaken for content.
                    transcript=item.transcript,
                    creator_id=args.creator,
                    language=item.labels.get("language", "hinglish"),
                    genres=[item.labels.get("genre", "general")],
                    tags=[str(t)[:40] for t in (item.labels.get("tags") or [])][:8]
                    + ["audio-ingest"],
                    duration_seconds=max(60, int(item.duration_seconds)),
                    chapters=episodes_for(item.duration_seconds),
                    source=ContentSource.PLATFORM,
                    is_synthetic=False,
                    published_at=utcnow(),
                    popularity={
                        "audio_sha256": item.sha256,
                        "source_file": path.name,
                        "drm_protected": item.drm,
                        "transcript_available": bool(item.transcript),
                        "duplicate_of_files": [q.name for q in by_hash[item.sha256]],
                        "source": "audio_ingest",
                    },
                )
                created.append(content)

                if args.write_stories:
                    await stories.update_one(
                        {"_id": slug},
                        {"$set": {
                            "_id": slug, "storyId": slug, "title": title,
                            "description": content.description, "synopsis": content.description,
                            "genre": content.primary_genre, "language": content.language,
                            "author": args.creator, "narrator": args.creator,
                            "type": "audio_series", "format": "story",
                            "episodes": len(content.chapters),
                            "episodesReleased": len(content.chapters),
                            "avgEpisodeMinutes": EPISODE_SECONDS // 60,
                            "totalDurationMinutes": int(item.duration_seconds // 60),
                            "tags": content.tags, "source": "audio_ingest",
                            "sourceFile": path.name, "audioSha256": item.sha256,
                            "transcriptChars": len(item.transcript),
                            "createdAt": utcnow(), "updatedAt": utcnow(),
                        }},
                        upsert=True,
                    )

        await container.content_repo.upsert_many(created)
        logger.info("")
        logger.info("Ingested %d catalog items from %d unique recordings.",
                    len(created), len(unique))
        if args.write_stories:
            logger.info("Also written into the '%s' collection.", settings.stories_collection)

        _report_audio_duplicates(created)

        if args.screen:
            await _screen(container, created)

        logger.info("")
        logger.info("Next: POST /pipeline/run to embed and label the new items.")
        return 0
    finally:
        await gateway.close()


def _report_audio_duplicates(created: list[ContentItem]) -> None:
    """Group the ingested items by audio fingerprint.

    This is exact-duplicate detection on the asset itself. It needs no transcript and
    no decryption, so it works on DRM-protected uploads where every text signal is
    blind. Two files with the same hash are the same recording, whatever they are
    called.
    """
    groups: dict[str, list[ContentItem]] = {}
    for item in created:
        groups.setdefault(item.popularity.get("audio_sha256", ""), []).append(item)

    families = {h: rows for h, rows in groups.items() if len(rows) > 1}
    logger.info("")
    logger.info("AUDIO FINGERPRINT CHECK")
    if not families:
        logger.info("  No two ingested recordings share an audio fingerprint.")
        return
    logger.info("  %d duplicate families across %d items:",
                len(families), sum(len(r) for r in families.values()))
    for digest, rows in families.items():
        logger.info("    sha256 %s  --  %d identical recordings", digest[:16], len(rows))
        for row in rows:
            logger.info("        %-28s  file: %s",
                        row.title[:28], row.popularity.get("source_file"))


async def _screen(container, created: list[ContentItem]) -> None:
    """Run each ingested item through the gate against everything else."""
    logger.info("")
    logger.info("Screening the ingested audio against the catalog...")
    catalog = await container.content_repo.iter_all(with_transcript=True)
    profiles = await container.profile_repo.all_by_id()
    if not profiles:
        logger.warning("No profiles yet, so the gate has nothing to compare against.")
        logger.warning("Run POST /pipeline/run first, then re-run with --screen.")
        return

    for item in created:
        report = await container.similarity.screen(
            SimilarityCandidate(
                title=item.title, description=item.description, transcript=item.transcript,
                language=item.language, genres=item.genres, chapters=item.chapters,
            ),
            catalog, profiles, top_k=2, exclude_content_id=item.content_id, use_llm=False,
        )
        top = report.matches[0] if report.matches else None
        logger.info(
            "  %-34s %-6s %-16s score=%.3f%s",
            item.title[:34], report.risk.value.upper(), report.duplicate_kind.value,
            report.top_score,
            f"  ~ {top.title[:28]}" if top else "",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcribe audio and ingest it into the catalog.")
    parser.add_argument("--source", required=True, help="Directory holding the audio files.")
    parser.add_argument("--apply", action="store_true", help="Transcribe and write.")
    parser.add_argument("--screen", action="store_true", help="Run the similarity gate afterwards.")
    parser.add_argument("--creator", default="audio-ingest", help="Creator to attribute these to.")
    parser.add_argument(
        "--no-stories", dest="write_stories", action="store_false",
        help="Do not write into the upstream stories collection.",
    )
    parser.set_defaults(write_stories=True)
    raise SystemExit(asyncio.run(main(parser.parse_args())))
