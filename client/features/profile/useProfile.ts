"use client";

import { api } from "@/lib/apiClient";
import { useAsync } from "@/lib/useAsync";
import type { TasteProfile } from "@/lib/types";

/** Loads the derived taste profile for a user; re-runs when `refreshKey` bumps. */
export function useProfile(userId: string | null, refreshKey: number) {
  return useAsync<TasteProfile>(
    () => api.profile(userId as string),
    [userId, refreshKey],
    Boolean(userId),
  );
}
