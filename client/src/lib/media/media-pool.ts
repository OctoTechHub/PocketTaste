// Media resolver. Everything here comes from the backend — no hardcoded audio.
//
// Audio is NOT resolved here: real narration is served by the API at
// GET /catalog/{id}/audio (Sarvam TTS, base64 WAV) and wired in on the watch page via
// useAudioClip. This module used to hash the content id into a pool of stock
// instrumental tracks so that every tile "played", which read as a broken product and
// hid the fact that the catalogue had no audio at all. A story with no narration
// simply has no audio — we never substitute a placeholder track.
//
// Cover/banner reconstruct the exact picsum URL the upstream `stories` docs store
// (seeded by content_id), so a tile shows the same art the catalog holds.

/**
 * No hardcoded audio — narration comes from the backend or not at all.
 *
 * The content id is accepted but ignored, so existing call sites that still pass one
 * keep compiling; nothing is derived from it.
 */
export function mediaFor(_contentId?: string): undefined {
  return undefined;
}

/** Cover art — the same seed the upstream `stories.coverImage` uses. */
export function coverFor(contentId: string): string {
  return `https://picsum.photos/seed/${encodeURIComponent(contentId)}/400/600`;
}

/** Wide banner — the same seed the upstream `stories.banner` uses. */
export function bannerFor(contentId: string): string {
  return `https://picsum.photos/seed/${encodeURIComponent(contentId)}-b/1280/720`;
}
