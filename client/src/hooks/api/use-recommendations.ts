"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import { useAuth } from "./use-auth";
import { recommendationsApi } from "@/lib/api/endpoints";
import { recommendationToItem } from "@/lib/api/mappers";
import type {
  MyRecommendationRequest,
  RecommendationRequest,
} from "@/lib/api/types";

/**
 * POST /me/recommendations — the "For You" rail for the signed-in listener.
 * Declarative: fetched on mount and re-run when the request changes. Disabled
 * while signed out, since the endpoint is authenticated.
 */
export function useMyRecommendations(
  body: MyRecommendationRequest = { limit: 12 },
  enabled = true,
) {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: ["me", "recommendations", body],
    queryFn: () => recommendationsApi.forMe(body),
    enabled: enabled && isAuthenticated,
    select: (result) => ({
      ...result,
      items: (result.items ?? []).map(recommendationToItem),
    }),
  });
}

/**
 * POST /recommendations — rank for an explicit user id (works anonymously,
 * cold-starts unknown users). Exposed as a mutation for on-demand ranking.
 */
export function useRecommendMutation() {
  return useMutation({
    mutationFn: (body: RecommendationRequest) =>
      recommendationsApi.forUser(body),
  });
}
