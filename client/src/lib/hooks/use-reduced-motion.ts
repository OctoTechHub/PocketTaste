"use client";

import { useEffect, useState } from "react";

/**
 * SSR-safe replacement for `motion/react`'s `useReducedMotion`.
 *
 * The library's hook reads `window.matchMedia("(prefers-reduced-motion: reduce)")`
 * synchronously on the client's very first render, but the server has no
 * `window` and always renders as if motion were NOT reduced. When a visitor's
 * OS actually has reduced-motion on, that first client render disagrees with
 * the server-rendered HTML before hydration effects ever run — a textbook
 * "branch on a browser-only value during render" hydration mismatch.
 *
 * Mirrors `useHoverCapable`: default `false` (matching the server), then
 * subscribe to the real media query in an effect, exactly like a listener on
 * any other external system — a harmless post-hydration update instead of a
 * mismatch.
 */
export function useSafeReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(mq.matches);
    update();
    mq.addEventListener?.("change", update);
    return () => mq.removeEventListener?.("change", update);
  }, []);

  return reduced;
}
