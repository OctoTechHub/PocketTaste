"use client";

import { useEffect, useRef, type RefObject } from "react";

import { usePlaybackLogger } from "./use-activity";

/**
 * Binds a <video> element to the activity log. Attaches native media listeners
 * and translates them into POST /activity events for the given content:
 *   - first play            -> "play"
 *   - reaching the end       -> "complete"
 *   - leaving mid-way (>5s)  -> "drop_off" at the last position
 *
 * All side effects live here, per the app's separation-of-concerns rule; the
 * watch view only supplies a ref and the content id.
 */
export function usePlaybackTracking(
  ref: RefObject<HTMLVideoElement | null>,
  contentId: string | undefined,
) {
  const log = usePlaybackLogger(contentId);
  // Latest values without re-subscribing listeners on every render.
  const state = useRef({ played: false, completed: false, position: 0 });

  useEffect(() => {
    const el = ref.current;
    if (!el || !contentId) return;

    state.current = { played: false, completed: false, position: 0 };

    const onPlay = () => {
      if (state.current.played) return;
      state.current.played = true;
      log.play(Math.floor(el.currentTime));
    };
    const onTimeUpdate = () => {
      state.current.position = el.currentTime;
    };
    const onEnded = () => {
      state.current.completed = true;
      log.complete();
    };

    el.addEventListener("play", onPlay);
    el.addEventListener("timeupdate", onTimeUpdate);
    el.addEventListener("ended", onEnded);

    return () => {
      el.removeEventListener("play", onPlay);
      el.removeEventListener("timeupdate", onTimeUpdate);
      el.removeEventListener("ended", onEnded);

      // Left before the end after watching a meaningful chunk → drop-off.
      const { played, completed, position } = state.current;
      if (played && !completed && position > 5) {
        log.dropOff(Math.floor(position));
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contentId]);
}

/** Convenience: create the ref alongside the tracking binding. */
export function usePlaybackRef(contentId: string | undefined) {
  const ref = useRef<HTMLVideoElement | null>(null);
  usePlaybackTracking(ref, contentId);
  return ref;
}
