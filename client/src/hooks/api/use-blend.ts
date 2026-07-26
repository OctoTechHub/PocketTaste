"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "./use-auth";
import { blendApi } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";

/** GET /blend — every blend the signed-in listener is part of. */
export function useBlends() {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: queryKeys.blends,
    queryFn: blendApi.list,
    enabled: isAuthenticated,
  });
}

/**
 * GET /blend/{id}/feed — the blended feed.
 *
 * Ranking two people against the whole catalog is real work on the server, so the
 * result is held rather than refetched on every focus change.
 */
export function useBlendFeed(blendId: string | null, limit = 18) {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: queryKeys.blendFeed(blendId ?? "none", limit),
    queryFn: () => blendApi.feed(blendId as string, limit),
    enabled: isAuthenticated && Boolean(blendId),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}

/** POST /blend — start a blend with the person at this address. */
export function useCreateBlend() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (email: string) => blendApi.create(email),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.blends }),
  });
}

/** DELETE /blend/{id} */
export function useRemoveBlend() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (blendId: string) => blendApi.remove(blendId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.blends }),
  });
}
