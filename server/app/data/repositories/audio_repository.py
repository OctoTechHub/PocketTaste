"""Narrated audio, stored apart from the catalogue item it belongs to.

Audio used to live on the `content_items` document. Narrating the catalogue put 29 MB
of base64 WAV in there and broke listing outright: MongoDB applies a sort *before* the
projection, so `.sort("published_at")` blew the 32 MB in-memory sort limit even though
`audio_base64` was excluded from the result. Every full read — cache warm-up,
similarity screening — was also dragging that payload across the wire for no reason.

A blob that is fetched by one endpoint, on demand, does not belong on the document
that every other query touches.
"""

from __future__ import annotations

from app.core.clock import utcnow
from app.data.mongo import Collections
from app.data.repositories.base import BaseRepository
from app.domain.models import ContentAudio


class ContentAudioRepository(BaseRepository[ContentAudio]):
    collection_name = Collections.AUDIO
    model_type = ContentAudio
    key_field = "content_id"

    async def save(
        self, content_id: str, *, audio_base64: str, language: str, source: str
    ) -> None:
        await self.collection.update_one(
            {"content_id": content_id},
            {
                "$set": {
                    "content_id": content_id,
                    "audio_base64": audio_base64,
                    "language": language,
                    "source": source,
                    "format": "wav",
                    "bytes": int(len(audio_base64) * 0.75),
                    "created_at": utcnow(),
                }
            },
            upsert=True,
        )

    async def ids_with_audio(self) -> set[str]:
        """Just the keys — never the blobs."""
        return {
            document["content_id"]
            async for document in self.collection.find({}, {"content_id": 1})
        }
