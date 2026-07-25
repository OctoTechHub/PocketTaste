"use client";

import { useQuery } from "@tanstack/react-query";

import type { ContentItem, ContentRow } from "@/data/content";
import { catalogApi } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import { contentToItem } from "@/lib/api/mappers";
import type { CatalogQuery, ContentResponse } from "@/lib/api/types";

/** GET /catalog — browse the catalog, mapped to UI ContentItem[]. */
export function useCatalog(params: CatalogQuery = {}) {
  return useQuery({
    queryKey: queryKeys.catalog(params),
    queryFn: () => catalogApi.list(params),
    select: (items) => items.map(contentToItem),
  });
}

/** GET /catalog/{id} — one item with its derived profile and features. */
export function useContent(contentId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.content(contentId ?? ""),
    queryFn: () => catalogApi.get(contentId as string),
    enabled: Boolean(contentId),
  });
}

function titleCase(value: string): string {
  return value ? value[0].toUpperCase() + value.slice(1) : value;
}

/** Group the raw catalog into genre shelves and pick a hero, for the home page. */
function buildRows(items: ContentResponse[]): {
  rows: ContentRow[];
  hero: ContentItem | null;
} {
  const byGenre = new Map<string, ContentResponse[]>();
  for (const item of items) {
    const key = item.genres[0] ?? item.language ?? "other";
    const bucket = byGenre.get(key);
    if (bucket) bucket.push(item);
    else byGenre.set(key, [item]);
  }

  const rows: ContentRow[] = Array.from(byGenre.entries())
    .map(([genre, list]) => ({
      id: genre,
      label: titleCase(genre),
      titles: list.map(contentToItem),
    }))
    // Fuller shelves first so the page opens strong.
    .sort((a, b) => b.titles.length - a.titles.length);

  const hero = items.length ? contentToItem(items[0]) : null;
  return { rows, hero };
}

/**
 * GET /catalog (broad) grouped into genre rows + a hero — the whole home page
 * feed, straight from the backend. No mock data.
 */
export function useCatalogRows(limit = 200) {
  const params: CatalogQuery = { limit };
  return useQuery({
    queryKey: [...queryKeys.catalog(params), "rows"],
    queryFn: () => catalogApi.list(params),
    select: buildRows,
  });
}
