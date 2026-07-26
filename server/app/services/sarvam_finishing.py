"""Sarvam AI finishing stage — the last step of the creator content pipeline.

Runs only after `StorytellingService.draft()` has produced prose AND the
similarity/plagiarism gate has cleared it (see `storytelling.py`). Three
independent, best-effort steps:

    1. polish   - same-language editorial pass, via Sarvam's chat model
    2. localize - machine translation into an Indic language, via Sarvam's Translate API
    3. narrate  - text-to-speech, via Sarvam's Bulbul TTS API

`polish` reuses `LlmService` (Sarvam's chat endpoint is OpenAI-compatible). `localize`
and `narrate` are native Sarvam REST endpoints — not OpenAI-shaped — so they go
through a plain `httpx` client instead.

Every method reports `ran: False` with a `reason` rather than raising, so a missing
or expired Sarvam key never fails the GOAT draft that already succeeded upstream.
"""

from __future__ import annotations

import base64
import io
import re
import wave

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.services.llm import LlmService

logger = get_logger(__name__)

#: Sarvam's Translate and TTS APIs key languages by BCP-47-ish locale, not our
#: plain ISO codes.
_LOCALE = {
    "en": "en-IN",
    "hi": "hi-IN",
    "ta": "ta-IN",
    "te": "te-IN",
    "bn": "bn-IN",
    "mr": "mr-IN",
    "kn": "kn-IN",
    "gu": "gu-IN",
    "ml": "ml-IN",
    "pa": "pa-IN",
    "od": "od-IN",
    # Hinglish is Hindi written in Latin script, not a separate language, and it is
    # how 39 of the catalogue's stories are stored. Bulbul reads romanised Hindi with
    # the hi-IN voice; without this row every one of those stories is refused as
    # "unsupported_language" and silently ends up with no narration at all.
    "hinglish": "hi-IN",
    "hi-en": "hi-IN",
}

#: Sarvam rejects a single Translate call over ~1000 characters.
_TRANSLATE_CHUNK_CHARS = 900
#: Sarvam rejects a single TTS input over ~500 characters.
_TTS_CHUNK_CHARS = 450

_POLISH_PROMPT = """You are copy-editing a drafted audio-story scene for a creator. Improve
clarity, pacing, and voice for read-aloud narration WITHOUT changing the plot, characters,
names or facts. Return only the revised scene text, nothing else — no preamble, no notes.

Scene:
{text}"""


def _merge_wav_clips(clips_base64: list[str]) -> str | None:
    """Concatenate same-format WAV clips into one playable file.

    Every clip in a `narrate()` call comes from the same TTS request configuration
    (speaker, model, target language), so they share sample rate, channel count and
    bit depth. That makes this a plain PCM-frame concatenation with one rewritten
    header — not a byte-level splice, which would corrupt the audio. Returns None
    if a clip fails to decode or the formats actually differ, so the caller can
    fall back to reporting the clips separately instead of serving a broken file.
    """
    if not clips_base64:
        return None
    try:
        frames: list[bytes] = []
        params: tuple | None = None
        for encoded in clips_base64:
            with wave.open(io.BytesIO(base64.b64decode(encoded))) as reader:
                clip_params = reader.getparams()[:4]  # nchannels, sampwidth, framerate, nframes
                if params is None:
                    params = clip_params
                elif clip_params[:3] != params[:3]:
                    logger.warning("Sarvam TTS clips have mismatched formats; cannot merge")
                    return None
                frames.append(reader.readframes(reader.getnframes()))

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as writer:
            nchannels, sampwidth, framerate, _ = params
            writer.setnchannels(nchannels)
            writer.setsampwidth(sampwidth)
            writer.setframerate(framerate)
            for chunk in frames:
                writer.writeframes(chunk)
        return base64.b64encode(buffer.getvalue()).decode("ascii")
    except (wave.Error, EOFError) as exc:
        logger.warning("Failed to merge Sarvam TTS clips: %s", exc)
        return None


def _chunk_text(text: str, limit: int) -> list[str]:
    """Split on sentence boundaries, packing as much as fits under `limit` per chunk."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) > limit and current:
            chunks.append(current)
            current = sentence[:limit]
        else:
            current = candidate[:limit]
    if current:
        chunks.append(current)
    return chunks or [text[:limit]]


class SarvamFinishingService:
    def __init__(self, settings: Settings, llm: LlmService) -> None:
        self._settings = settings
        self._llm = llm
        self._client = (
            httpx.AsyncClient(
                base_url=settings.sarvam_api_base,
                headers={"api-subscription-key": settings.sarvam_api_key},
                timeout=settings.llm_timeout_seconds,
            )
            if settings.sarvam_enabled
            else None
        )

    @property
    def available(self) -> bool:
        return self._client is not None

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    @staticmethod
    def locale_code(language: str) -> str | None:
        return _LOCALE.get(language.strip().lower())

    def describe(self) -> dict:
        return {
            "available": self.available,
            "polish": {"model": self._settings.sarvam_model} if self.available else None,
            "localize": {"endpoint": "/translate"} if self.available else None,
            "narrate": {
                "endpoint": "/text-to-speech",
                "speaker": self._settings.sarvam_tts_speaker,
                "model": self._settings.sarvam_tts_model,
            }
            if self.available
            else None,
            "supported_languages": sorted(_LOCALE),
            "reason": None if self.available else "SARVAM_API_KEY not configured",
        }

    # --- stage 1: same-language polish --------------------------------------

    async def polish(self, text: str) -> dict:
        """Editorial pass through Sarvam's own chat model, regardless of source language."""
        if not text.strip():
            return {"ran": False, "reason": "empty_input"}
        if not self._settings.sarvam_enabled:
            return {"ran": False, "reason": "sarvam_not_configured"}
        result = await self._llm.complete_text(
            _POLISH_PROMPT.format(text=text[:6000]),
            provider="sarvam",
            # sarvam-30b is a reasoning model: it spends tokens on reasoning_content
            # before the actual reply, and verified live testing shows it can burn
            # 1500+ tokens reasoning about a single sentence even at
            # reasoning_effort="low" — there is no reliable budget that guarantees
            # non-empty content. `polish` degrades to the original text below when
            # that happens, so this is a soft no-op, not a failure.
            max_tokens=min(4000, max(1200, int(len(text.split()) * 3))),
            temperature=0.3,
        )
        if not result.ok or not result.text:
            return {"ran": False, "reason": result.error or "empty_response"}
        return {"ran": True, "model": result.model, "text": result.text}

    # --- stage 2: Indic localization -----------------------------------------

    async def localize(self, text: str, *, source_language: str, target_language: str) -> dict:
        """Machine-translate into an Indic language via Sarvam's Translate API."""
        if not text.strip():
            return {"ran": False, "reason": "empty_input"}
        if not self.available:
            return {"ran": False, "reason": "sarvam_not_configured"}
        target = self.locale_code(target_language)
        if target is None:
            return {"ran": False, "reason": f"unsupported_target_language:{target_language}"}
        source = self.locale_code(source_language) or "en-IN"
        if source == target:
            return {"ran": False, "reason": "source_and_target_identical"}

        chunks = _chunk_text(text, _TRANSLATE_CHUNK_CHARS)
        translated: list[str] = []
        try:
            for chunk in chunks:
                response = await self._client.post(
                    "/translate",
                    json={
                        "input": chunk,
                        "source_language_code": source,
                        "target_language_code": target,
                        "mode": "modern-colloquial",
                    },
                )
                response.raise_for_status()
                translated.append(response.json().get("translated_text", ""))
        except httpx.HTTPError as exc:
            logger.error("Sarvam translate call failed: %s", exc)
            return {"ran": bool(translated), "reason": f"translate_error: {exc}", "text": " ".join(translated)}

        return {
            "ran": True,
            "language": target_language,
            "locale_code": target,
            "text": " ".join(part for part in translated if part),
            "chunks_translated": len(translated),
            "model": "sarvam-translate",
        }

    # --- stage 3: TTS narration ------------------------------------------------

    async def narrate(self, text: str, *, language: str) -> dict:
        """Text-to-speech via Sarvam's Bulbul model.

        Each chunk is synthesised independently (the API caps input length), then
        merged into one playable WAV (`audio_base64`) since every chunk shares the
        same format. `clips` is kept too, so a format mismatch (caller can still see
        what was synthesised even if the merge itself has to fall back.
        """
        if not text.strip():
            return {"ran": False, "reason": "empty_input"}
        if not self.available:
            return {"ran": False, "reason": "sarvam_not_configured"}
        target = self.locale_code(language)
        if target is None:
            return {"ran": False, "reason": f"unsupported_language:{language}"}

        clips: list[dict] = []
        try:
            for index, chunk in enumerate(_chunk_text(text, _TTS_CHUNK_CHARS), start=1):
                response = await self._client.post(
                    "/text-to-speech",
                    json={
                        "inputs": [chunk],
                        "target_language_code": target,
                        "speaker": self._settings.sarvam_tts_speaker,
                        "model": self._settings.sarvam_tts_model,
                    },
                )
                response.raise_for_status()
                audios = response.json().get("audios") or []
                if audios:
                    clips.append({"sequence": index, "chars": len(chunk), "audio_base64": audios[0]})
        except httpx.HTTPError as exc:
            logger.error("Sarvam TTS call failed: %s", exc)
            return {"ran": bool(clips), "reason": f"tts_error: {exc}", "clips": clips}

        merged = _merge_wav_clips([clip["audio_base64"] for clip in clips])
        return {
            "ran": bool(clips),
            "language": language,
            "locale_code": target,
            "speaker": self._settings.sarvam_tts_speaker,
            "model": self._settings.sarvam_tts_model,
            "format": "wav",
            "clip_count": len(clips),
            "audio_base64": merged,
            "merged": merged is not None,
            "clips": clips,
            "note": (
                "audio_base64 is all clips merged into one WAV file."
                if merged is not None
                else "Clip formats did not match, so audio_base64 is unset; see clips for the "
                "individual chunks."
            ),
        }

    # --- orchestration --------------------------------------------------------

    async def finish(
        self,
        text: str,
        *,
        source_language: str,
        target_language: str | None,
        narrate: bool,
    ) -> dict:
        """Run all requested finishing steps and return one auditable block.

        `target_language` triggers localization; `narrate` triggers TTS on the best
        text available (localized if produced, else the polished/original text) in
        that same final language.
        """
        if not self._settings.sarvam_enabled:
            return {
                "available": False,
                "reason": "SARVAM_API_KEY not configured",
                "polish": {"ran": False, "reason": "sarvam_not_configured"},
                "localize": {"ran": False, "reason": "sarvam_not_configured"},
                "narrate": {"ran": False, "reason": "sarvam_not_configured"},
            }

        polish_result = await self.polish(text)
        best_text = polish_result["text"] if polish_result.get("ran") else text
        final_language = source_language

        localize_result: dict = {"ran": False, "reason": "not_requested"}
        if target_language:
            localize_result = await self.localize(
                best_text, source_language=source_language, target_language=target_language
            )
            if localize_result.get("ran"):
                best_text = localize_result["text"]
                final_language = target_language

        narrate_result: dict = {"ran": False, "reason": "not_requested"}
        if narrate:
            narrate_result = await self.narrate(best_text, language=final_language)

        return {
            "available": True,
            "final_language": final_language,
            "polish": polish_result,
            "localize": localize_result,
            "narrate": narrate_result,
        }
