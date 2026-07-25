"use client";

import { useQuery } from "@tanstack/react-query";

import { analyticsApi } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";

/** GET /analytics/content/{id} — retention curve, chapter interest, abandon point. */
export function useContentAnalytics(contentId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.analyticsContent(contentId ?? ""),
    queryFn: () => analyticsApi.content(contentId as string),
    enabled: Boolean(contentId),
  });
}

/** GET /analytics/content/{id}/drop-off — plain-English drop-off diagnosis. */
export function useContentDropOff(contentId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.analyticsDropOff(contentId ?? ""),
    queryFn: () => analyticsApi.contentDropOff(contentId as string),
    enabled: Boolean(contentId),
  });
}

/** GET /analytics/user/{id} — derived listener taste profile. */
export function useUserAnalytics(userId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.analyticsUser(userId ?? ""),
    queryFn: () => analyticsApi.user(userId as string),
    enabled: Boolean(userId),
  });
}

/** GET /analytics/creators/{id} — portfolio view for one creator. */
export function useCreatorAnalytics(creatorId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.analyticsCreator(creatorId ?? ""),
    queryFn: () => analyticsApi.creator(creatorId as string),
    enabled: Boolean(creatorId),
  });
}
