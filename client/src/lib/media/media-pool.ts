// Media resolver for artwork only.
//
// The backend catalog is an intelligence layer and carries no artwork, so covers and
// banners are seeded from content_id via picsum — the same convention the upstream
// `stories` docs use.
//
// Audio is deliberately NOT resolved here. This module used to hash the content id
// into a pool of stock instrumental tracks so that every tile "played". That was the
// wrong trade: a Hinglish horror story opening with royalty-free guitar reads as a
// broken product, and it concealed the fact that the catalogue had no audio at all.
//
// Real narration now exists — Sarvam Bulbul reads each story's own text in its own
// language — and it is served from `GET /catalog/{id}/audio`, fetched on the watch
// page. A story without narration renders as having none rather than borrowing
// someone else's music.

/** Always undefined: audio comes from the API, never from a stock pool. */
export function mediaFor(): undefined {
  return undefined;
}

/** Cover art — matches the upstream `stories.coverImage` seed convention. */
export function coverFor(contentId: string): string {
  return `https://picsum.photos/seed/${encodeURIComponent(contentId)}/400/600`;
}

/** Wide banner — matches the upstream `stories.banner` seed convention. */
export function bannerFor(contentId: string): string {
  return `https://picsum.photos/seed/${encodeURIComponent(contentId)}-b/1280/720`;
}
