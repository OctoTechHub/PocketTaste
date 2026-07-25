"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/apiClient";
import type { DiscoveryIntent, RankedSeries } from "@/lib/types";

interface DiscoveryState {
  query: string;
  intent: DiscoveryIntent | null;
  results: RankedSeries[];
  loading: boolean;
  error: string | null;
  active: boolean;
}

const EMPTY: DiscoveryState = {
  query: "",
  intent: null,
  results: [],
  loading: false,
  error: null,
  active: false,
};

/** Imperative conversational-discovery controller (runs on submit, not on mount). */
export function useDiscovery(userId: string | null) {
  const [state, setState] = useState<DiscoveryState>(EMPTY);

  const run = useCallback(
    async (query: string) => {
      const trimmed = query.trim();
      if (!trimmed) return;
      setState((s) => ({ ...s, query: trimmed, loading: true, error: null, active: true }));
      try {
        const { intent, results } = await api.discover(trimmed, userId ?? undefined);
        setState({ query: trimmed, intent, results, loading: false, error: null, active: true });
      } catch (err: unknown) {
        setState((s) => ({
          ...s,
          loading: false,
          error: err instanceof Error ? err.message : String(err),
        }));
      }
    },
    [userId],
  );

  const clear = useCallback(() => setState(EMPTY), []);

  return { ...state, run, clear };
}
