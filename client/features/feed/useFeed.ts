"use client";

import { api } from "@/lib/apiClient";
import { useAsync } from "@/lib/useAsync";
import type { FeedRail } from "@/lib/types";

/** Loads the personalized home feed for a user; re-runs when `refreshKey` bumps. */
export function useFeed(userId: string | null, refreshKey: number) {
  return useAsync<FeedRail[]>(
    () => api.feed(userId as string),
    [userId, refreshKey],
    Boolean(userId),
  );
}
