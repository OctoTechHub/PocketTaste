// Media resolver. The backend catalog is an intelligence layer with no media
// URLs, so we join each story to a real, streamable asset by content_id.
//
// Everything here is a PUBLIC url (no local files), so it works unchanged once
// deployed:
//   - cover / banner : picsum.photos, seeded by content_id (same convention the
//                      upstream `stories` docs use)
//   - audio          : a public, Range-enabled CDN track, picked deterministically
//
// This is the "join by content_id" pattern — catalog from the API, media from a
// public CDN — so every tile has art and every story actually plays.

/** Public, CORS-safe, Range-enabled audio tracks (SoundHelix hosts 1..17). */
const AUDIO_POOL: string[] = Array.from(
  { length: 17 },
  (_, i) => `https://www.soundhelix.com/examples/mp3/SoundHelix-Song-${i + 1}.mp3`,
);

/** Stable 32-bit hash so a given content_id always maps to the same asset. */
function hash(seed: string): number {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h);
}

/** A public, streamable media URL for a story. */
export function mediaFor(contentId: string): string | undefined {
  if (!AUDIO_POOL.length) return undefined;
  return AUDIO_POOL[hash(contentId) % AUDIO_POOL.length];
}

/** Cover art — matches the upstream `stories.coverImage` seed convention. */
export function coverFor(contentId: string): string {
  return `https://picsum.photos/seed/${encodeURIComponent(contentId)}/400/600`;
}

/** Wide banner — matches the upstream `stories.banner` seed convention. */
export function bannerFor(contentId: string): string {
  return `https://picsum.photos/seed/${encodeURIComponent(contentId)}-b/1280/720`;
}
