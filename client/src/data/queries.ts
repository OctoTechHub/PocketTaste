// Read-side helpers over the unified catalog. Pure, no side effects.
import type { ContentItem } from "./content";
import { allItems } from "./catalog";

export function getVideo(id: string): ContentItem | undefined {
  return allItems.find((item) => item.id === id);
}

/** Recommendations for an item: everything else, rotated so each page differs. */
export function getRecommendations(id: string, n = 18): ContentItem[] {
  const idx = Math.max(0, allItems.findIndex((item) => item.id === id));
  const rest = allItems.filter((item) => item.id !== id);
  return [...rest.slice(idx), ...rest.slice(0, idx)].slice(0, n);
}

export { allItems as allVideos };
