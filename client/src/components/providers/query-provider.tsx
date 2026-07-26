"use client";

import {
  keepPreviousData,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

/**
 * Owns the single React Query client for the app. Created once per browser
 * session via useState so fast-refresh and re-renders never swap the cache.
 *
 * Tuned so switching Studio tabs is seamless: data is cached long enough that a
 * tab you've already opened re-shows instantly with no loader or refetch flash,
 * and in-flight requests are never re-fired just because a panel remounted.
 */
export function QueryProvider({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5 * 60_000, // 5 min — a re-opened tab serves cache
            gcTime: 30 * 60_000, // keep results around while navigating
            retry: 1,
            refetchOnWindowFocus: false,
            refetchOnMount: false, // remount uses cache instead of re-fetching
            placeholderData: keepPreviousData, // no empty flash when params change
          },
        },
      }),
  );

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
