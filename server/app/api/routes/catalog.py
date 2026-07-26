"""Catalog ingestion and browsing."""

from __future__ import annotations

import base64

from fastapi import APIRouter, Query, Request, Response, status

from app.api.deps import CurrentAccount, StorageDep
from app.core.errors import NotFoundError
from app.domain.schemas import (
    ContentCreate,
    ContentDetailResponse,
    ContentIngestResponse,
    ContentResponse,
)

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("", response_model=list[ContentResponse], summary="Browse the catalog")
async def list_catalog(
    container: StorageDep,
    language: str | None = Query(default=None),
    genre: str | None = Query(default=None),
    creator_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ContentResponse]:
    items = await container.content_repo.list_catalog(
        language=language, genre=genre, creator_id=creator_id, limit=limit, offset=offset
    )
    return [ContentResponse.from_domain(item) for item in items]


@router.post(
    "",
    response_model=ContentIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a story (screened for duplication before it is stored)",
)
async def create_content(
    payload: ContentCreate,
    container: StorageDep,
    account: CurrentAccount,
    screen: bool = Query(default=True, description="Run the similarity gate before storing."),
) -> ContentIngestResponse:
    """Rejects with 409 and the full similarity report when the gate returns `block`.

    The upload is attributed to the signed-in creator: `creator_id` in the body is
    ignored, so an upload cannot be filed under someone else's name.
    """
    payload = payload.model_copy(update={"creator_id": account.user_id})
    item, report = await container.catalog_service.ingest(
        payload, screen=screen, use_llm=container.llm.available
    )
    container.cache.invalidate()
    return ContentIngestResponse(
        content_id=item.content_id,
        created=True,
        similarity_gate=report.model_dump(mode="json") if report else None,
        profile_queued=True,
    )


@router.get("/{content_id}", response_model=ContentDetailResponse, summary="One item with its derived state")
async def get_content(content_id: str, container: StorageDep) -> ContentDetailResponse:
    item = await container.catalog_service.get_detail(content_id)
    return ContentDetailResponse(
        content=ContentResponse.from_domain(item),
        chapters=item.chapters,
        profile=await container.profile_repo.get(content_id),
        features=await container.features_repo.get(content_id),
    )


@router.get("/{content_id}/transcript", summary="Raw transcript")
async def get_transcript(content_id: str, container: StorageDep) -> dict:
    item = await container.content_repo.get(content_id)
    if item is None:
        raise NotFoundError(f"No catalog item with id '{content_id}'.")
    return {"content_id": content_id, "title": item.title, "transcript": item.transcript}


@router.get("/{content_id}/audio", summary="Narrated audio, if any (base64 WAV)")
async def get_audio(content_id: str, container: StorageDep) -> dict:
    """Empty `audio_base64` means this item was never narrated through the copilot —
    this endpoint is not a general media host, only the Sarvam finishing output."""
    item = await container.content_repo.get(content_id)
    if item is None:
        raise NotFoundError(f"No catalog item with id '{content_id}'.")
    # The blob lives in its own collection so it never rides along with catalogue
    # reads; only this endpoint pays for it.
    clip = await container.audio_repo.get(content_id)
    return {
        "content_id": content_id,
        "title": item.title,
        "has_audio": clip is not None,
        "format": clip.format if clip else None,
        "language": clip.language if clip else item.audio_language,
        "source": clip.source if clip else item.audio_source,
        "bytes": clip.bytes if clip else 0,
        "audio_base64": clip.audio_base64 if clip else "",
    }


@router.get("/{content_id}/audio.wav", summary="Narrated audio as a streamable file (Range-capable)")
async def stream_audio(content_id: str, request: Request, container: StorageDep) -> Response:
    """Streams the narrated clip as real audio bytes so the player can start
    immediately and seek — instead of shipping a ~15MB base64 blob to the client
    and stuffing it into a data: URI."""
    clip = await container.audio_repo.get(content_id)
    if clip is None or not clip.audio_base64:
        raise NotFoundError(f"No narrated audio for '{content_id}'.")

    data = base64.b64decode(clip.audio_base64)
    total = len(data)
    fmt = (clip.format or "wav").lower()
    media_type = "audio/wav" if fmt in ("wav", "x-wav") else f"audio/{fmt}"
    base_headers = {"Accept-Ranges": "bytes", "Cache-Control": "public, max-age=3600"}

    range_header = request.headers.get("range")
    if range_header and range_header.startswith("bytes="):
        start_s, _, end_s = range_header.removeprefix("bytes=").partition("-")
        start = int(start_s) if start_s.isdigit() else 0
        end = int(end_s) if end_s.isdigit() else total - 1
        end = min(end, total - 1)
        if start > end or start >= total:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{total}"})
        chunk = data[start : end + 1]
        return Response(
            content=chunk,
            status_code=206,
            media_type=media_type,
            headers={**base_headers, "Content-Range": f"bytes {start}-{end}/{total}",
                     "Content-Length": str(len(chunk))},
        )

    return Response(content=data, media_type=media_type,
                    headers={**base_headers, "Content-Length": str(total)})
