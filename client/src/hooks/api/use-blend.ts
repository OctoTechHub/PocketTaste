"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "./use-auth";
import { API_BASE_URL } from "@/lib/api/config";
import { blendApi } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import { getToken } from "@/lib/api/token-store";
import type { BlendFeed } from "@/lib/api/types";

export interface BlendStage {
  step: string;
  message: string;
  elapsed_ms: number;
  [key: string]: unknown;
}

/**
 * Streams the blend as the server computes it.
 *
 * `EventSource` cannot send an Authorization header, so this reads the SSE body off
 * `fetch` and splits it by hand. Stages arrive as the algorithm finishes each one;
 * the final `result` frame carries the same payload the non-streaming endpoint
 * returns, so nothing has to be fetched twice.
 */
export function useBlendStream(blendId: string | null, limit = 18) {
  const [stages, setStages] = useState<BlendStage[]>([]);
  const [feed, setFeed] = useState<BlendFeed | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const run = useCallback(async () => {
    if (!blendId) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStages([]);
    setFeed(null);
    setError(null);
    setIsStreaming(true);

    try {
      const response = await fetch(
        `${API_BASE_URL}/blend/${blendId}/feed/stream?limit=${limit}`,
        {
          headers: { Authorization: `Bearer ${getToken() ?? ""}` },
          signal: controller.signal,
        },
      );
      if (!response.ok || !response.body) {
        throw new Error(`The blend could not be built (${response.status}).`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE frames are separated by a blank line. Keep the trailing partial.
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";

        for (const frame of frames) {
          const line = frame.split("\n").find((part) => part.startsWith("data: "));
          if (!line) continue;
          const payload = JSON.parse(line.slice(6));
          if (payload.type === "stage") {
            setStages((current) => [...current, payload as BlendStage]);
          } else if (payload.type === "result") {
            setFeed(payload as BlendFeed);
          } else if (payload.type === "error") {
            setError(payload.message ?? "The blend failed.");
          }
        }
      }
    } catch (caught) {
      if ((caught as Error).name !== "AbortError") {
        setError((caught as Error).message || "The blend could not be built.");
      }
    } finally {
      setIsStreaming(false);
    }
  }, [blendId, limit]);

  useEffect(() => {
    void run();
    return () => abortRef.current?.abort();
  }, [run]);

  return { stages, feed, error, isStreaming, restart: run };
}

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
