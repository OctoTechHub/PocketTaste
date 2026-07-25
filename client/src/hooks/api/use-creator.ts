"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import { useAuth } from "./use-auth";
import {
  copilotApi,
  creatorApi,
  insightsApi,
  similarityApi,
} from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import type {
  SimilarityCheckRequest,
  StoryDraftRequest,
  StoryOutlineRequest,
} from "@/lib/api/types";

// --- Creator studio (authenticated) ----------------------------------------

/** GET /creator/opportunities — "what should I write next?" for this creator. */
export function useCreatorOpportunities(language?: string, limit = 5) {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: queryKeys.creatorOpportunities(language),
    queryFn: () => creatorApi.opportunities(limit, language),
    enabled: isAuthenticated,
  });
}

/** GET /creator/performance — per-story retention for this creator. */
export function useCreatorPerformance() {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: queryKeys.creatorPerformance,
    queryFn: () => creatorApi.performance(),
    enabled: isAuthenticated,
  });
}

// --- Platform insights (public) --------------------------------------------

/** GET /insights/opportunities — under-served genre/language cells. */
export function useOpportunities(limit = 10) {
  return useQuery({
    queryKey: queryKeys.insightsOpportunities(limit),
    queryFn: () => insightsApi.opportunities(limit),
  });
}

/** GET /insights/demand — supply/demand gap by genre and language. */
export function useDemand(refresh = false) {
  return useQuery({
    queryKey: queryKeys.insightsDemand,
    queryFn: () => insightsApi.demand(refresh),
  });
}

// --- Actions (mutations) ----------------------------------------------------

/** POST /similarity/check — screen a draft before upload. */
export function useSimilarityCheck() {
  return useMutation({
    mutationFn: (body: SimilarityCheckRequest) => similarityApi.check(body),
  });
}

/** POST /copilot/outline — screened, demand-anchored story outline. */
export function useCopilotOutline() {
  return useMutation({
    mutationFn: (body: StoryOutlineRequest) => copilotApi.outline(body),
  });
}

/** POST /copilot/draft — full GOAT chain: outline plus written scene text. */
export function useCopilotDraft() {
  return useMutation({
    mutationFn: (body: StoryDraftRequest) => copilotApi.draft(body),
  });
}
