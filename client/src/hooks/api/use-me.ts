"use client";

import { useQuery } from "@tanstack/react-query";

import { useAuth } from "./use-auth";
import { meApi } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";

/** GET /me/profile — the signed-in listener's derived taste profile. */
export function useMyProfile() {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: queryKeys.profile,
    queryFn: () => meApi.profile(),
    enabled: isAuthenticated,
  });
}

/** GET /me/history — the signed-in listener's own event log. */
export function useMyHistory(limit = 100) {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: queryKeys.history(limit),
    queryFn: () => meApi.history(limit),
    enabled: isAuthenticated,
  });
}
