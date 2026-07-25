"use client";

import { useMutation } from "@tanstack/react-query";
import { useCallback } from "react";

import { useAuth } from "./use-auth";
import { activityApi } from "@/lib/api/endpoints";
import type { ActivityCreate, EventType } from "@/lib/api/types";

/**
 * POST /activity — log one listening event (authenticated).
 *
 * This is the fuel for the whole recommendation/insight layer. The endpoint
 * requires a token and attributes the event to the token holder, so we no-op
 * when signed out rather than firing a doomed 401.
 */
export function useLogActivity() {
  const { isAuthenticated } = useAuth();
  return useMutation({
    mutationFn: (body: ActivityCreate) => {
      if (!isAuthenticated) {
        // Silently skip — anonymous playback isn't attributable.
        return Promise.resolve({
          accepted: 0,
          rejected: 0,
          event_ids: [],
          errors: [],
        });
      }
      return activityApi.log(body);
    },
  });
}

/**
 * Playback-scoped helper returning typed loggers for one piece of content,
 * so watch-view side effects read as `log.play()` / `log.dropOff(seconds)`.
 */
export function usePlaybackLogger(contentId: string | undefined) {
  const { mutate } = useLogActivity();

  const emit = useCallback(
    (event_type: EventType, extra: Partial<ActivityCreate> = {}) => {
      if (!contentId) return;
      mutate({ content_id: contentId, event_type, device: "web", ...extra });
    },
    [contentId, mutate],
  );

  return {
    play: (positionSeconds = 0) =>
      emit("play", { position_seconds: positionSeconds }),
    pause: (positionSeconds: number) =>
      emit("pause", { position_seconds: positionSeconds }),
    resume: (positionSeconds: number) =>
      emit("resume", { position_seconds: positionSeconds }),
    complete: () => emit("complete"),
    dropOff: (positionSeconds: number) =>
      emit("drop_off", { position_seconds: positionSeconds }),
    replay: () => emit("replay"),
  };
}
