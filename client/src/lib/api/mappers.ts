// Adapters from the server's DTOs to the UI's ContentItem shape, so the
// existing TitleCard / ContentRow components render backend data unchanged.
//
// The backend is an intelligence layer, not a media host: it carries no artwork
// or media URL. We therefore synthesise a deterministic gradient cover from the
// id, and leave `audio`/`url` for the app's own media source to fill by id.

import type { ContentItem } from "@/data/content";
import type {
  ContentResponse,
  DiscoveryHit,
  RecommendationItem,
} from "./types";

function hashHue(seed: string, salt = 0): number {
  let h = 2166136261 ^ salt;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h) % 360;
}

/** A stable two-stop gradient cover as an inline SVG data URI. */
export function coverFor(seed: string, label = ""): string {
  const h1 = hashHue(seed, 0);
  const h2 = (h1 + 48) % 360;
  const initial = (label.trim()[0] ?? "•").toUpperCase();
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="338" viewBox="0 0 600 338">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="hsl(${h1} 70% 22%)"/>
    <stop offset="1" stop-color="hsl(${h2} 65% 12%)"/>
  </linearGradient></defs>
  <rect width="600" height="338" fill="url(#g)"/>
  <text x="40" y="200" font-family="system-ui,sans-serif" font-size="180" font-weight="800" fill="hsl(${h1} 60% 78%)" fill-opacity="0.28">${initial}</text>
</svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

export function formatDuration(seconds: number): string {
  if (!seconds || seconds < 0) return "";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function contentToItem(c: ContentResponse): ContentItem {
  const cover = coverFor(c.content_id, c.title);
  const genre = c.genres[0] ?? c.language?.toUpperCase() ?? "";
  return {
    id: c.content_id,
    name: c.title,
    channel: c.creator_id || "PocketTaste",
    duration: formatDuration(c.duration_seconds),
    views: genre,
    thumb: cover,
    wideThumb: cover,
    url: `/watch/${c.content_id}`,
  };
}

export function recommendationToItem(r: RecommendationItem): ContentItem {
  const cover = coverFor(r.content_id, r.title);
  const genre = r.genres?.[0] ?? "";
  return {
    id: r.content_id,
    name: r.title,
    channel: r.reason ? "Recommended" : "PocketTaste",
    duration: "",
    views: genre || `${Math.round((r.final_score ?? 0) * 100)}% match`,
    thumb: cover,
    wideThumb: cover,
    url: `/watch/${r.content_id}`,
  };
}

export function hitToItem(h: DiscoveryHit): ContentItem {
  const cover = coverFor(h.content_id, h.title);
  return {
    id: h.content_id,
    name: h.title,
    channel: h.genres[0] ?? h.language?.toUpperCase() ?? "",
    duration: "",
    views: "",
    thumb: cover,
    wideThumb: cover,
    url: `/watch/${h.content_id}`,
  };
}
