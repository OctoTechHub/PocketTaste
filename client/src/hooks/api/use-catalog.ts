"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { ContentItem, ContentRow } from "@/data/content";
import { catalogApi } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import { contentToItem } from "@/lib/api/mappers";
import type { CatalogQuery, ContentCreate, ContentResponse } from "@/lib/api/types";

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

/** GET /catalog/{id}/transcript — the raw transcript for a story. */
export function useTranscript(contentId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ["catalog", "transcript", contentId ?? ""],
    queryFn: () => catalogApi.transcript(contentId as string),
    enabled: enabled && Boolean(contentId),
  });
}

/** GET /catalog/{id}/audio — narrated WAV (base64), if this item was voiced via the copilot. */
export function useAudioClip(contentId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ["catalog", "audio", contentId ?? ""],
    queryFn: () => catalogApi.audio(contentId as string),
    enabled: enabled && Boolean(contentId),
  });
}

/**
 * POST /catalog — upload a story. The upload is screened for duplication first
 * (409 + full similarity report when the gate blocks). The creator is taken
 * from the token; `creator_id` in the body is ignored server-side.
 */
export function useUploadContent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ body, screen = true }: { body: ContentCreate; screen?: boolean }) =>
      catalogApi.create(body, screen),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["catalog"] });
      qc.invalidateQueries({ queryKey: ["creator"] });
    },
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

/**
 * Stories narrated through the Studio copilot (Sarvam TTS), newest first. The
 * backend carries no "featured" concept — this is purely `has_audio` on
 * GET /catalog, since only copilot-published stories ever set it.
 */
export function useNewReleases(limit = 200) {
  const params: CatalogQuery = { limit };
  return useQuery({
    queryKey: [...queryKeys.catalog(params), "new-releases"],
    queryFn: () => catalogApi.list(params),
    select: (items) =>
      items
        .filter((item) => item.has_audio)
        .sort((a, b) => +new Date(b.published_at) - +new Date(a.published_at))
        .map(contentToItem),
  });
}
