"use client";

import { useMutation } from "@tanstack/react-query";

import { useAuth } from "./use-auth";
import { discoveryApi } from "@/lib/api/endpoints";
import { hitToItem } from "@/lib/api/mappers";
import type { DiscoveryRequest } from "@/lib/api/types";

/**
 * POST /discovery/search — natural-language catalog search.
 *
 * A search is an action (and the server logs zero-result queries as an
 * unmet-demand signal), so it's a mutation. When signed in we pass the user id
 * so the query is attributed to the listener.
 */
export function useSearch() {
  const { account } = useAuth();
  return useMutation({
    mutationFn: (body: Omit<DiscoveryRequest, "user_id">) =>
      discoveryApi.search({ ...body, user_id: account?.user_id ?? null }),
    // Map hits to UI items alongside the raw response for the answer/snippets.
    onSuccess: () => {},
  });
}

/** Convenience: map a search response's hits to UI ContentItem[]. */
export { hitToItem };
