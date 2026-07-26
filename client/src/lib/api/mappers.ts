// Adapters from the server's DTOs to the UI's ContentItem shape, so the existing
// TitleCard / Billboard / watch components render backend data unchanged.
//
// Media join: the backend carries no artwork or audio, so we resolve both from
// content_id — cover/banner via the upstream picsum seed, audio from the local
// LibriVox pool. Every tile gets real art and every story actually plays.

import type { ContentItem } from "@/data/content";
import { bannerFor, coverFor, mediaFor } from "@/lib/media/media-pool";
import type {
  ContentResponse,
  DiscoveryHit,
  RecommendationItem,
} from "./types";

export function formatDuration(seconds: number): string {
  if (!seconds || seconds < 0) return "";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/** "5881154" -> "5.9M plays". */
function playsLabel(popularity?: Record<string, unknown>): string {
  const plays = typeof popularity?.plays === "number" ? popularity.plays : 0;
  if (!plays) return "";
  const compact =
    plays >= 1_000_000
      ? `${(plays / 1_000_000).toFixed(1)}M`
      : plays >= 1_000
        ? `${(plays / 1_000).toFixed(0)}K`
        : String(plays);
  return `${compact} plays`;
}

function narrator(popularity?: Record<string, unknown>): string {
  return typeof popularity?.narrator === "string" ? popularity.narrator : "";
}

export function contentToItem(c: ContentResponse): ContentItem {
  const plays = playsLabel(c.popularity);
  return {
    id: c.content_id,
    name: c.title,
    channel: narrator(c.popularity) || c.creator_id || "PocketTaste",
    duration: formatDuration(c.duration_seconds),
    views: plays || c.genres[0] || c.language?.toUpperCase() || "",
    thumb: coverFor(c.content_id),
    wideThumb: bannerFor(c.content_id),
    url: `/watch/${c.content_id}`,
    audio: mediaFor(c.content_id),
    hasAudio: c.has_audio,
  };
}

export function recommendationToItem(r: RecommendationItem): ContentItem {
  const genre = r.genres?.[0] ?? "";
  return {
    id: r.content_id,
    name: r.title,
    channel: r.reason ? "Recommended" : "PocketTaste",
    duration: "",
    views: genre || `${Math.round((r.final_score ?? 0) * 100)}% match`,
    thumb: coverFor(r.content_id),
    wideThumb: bannerFor(r.content_id),
    url: `/watch/${r.content_id}`,
    audio: mediaFor(r.content_id),
  };
}

export function hitToItem(h: DiscoveryHit): ContentItem {
  return {
    id: h.content_id,
    name: h.title,
    channel: h.genres[0] ?? h.language?.toUpperCase() ?? "",
    duration: "",
    views: "",
    thumb: coverFor(h.content_id),
    wideThumb: bannerFor(h.content_id),
    url: `/watch/${h.content_id}`,
    audio: mediaFor(h.content_id),
  };
}
