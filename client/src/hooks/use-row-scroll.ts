"use client";

import { useRef } from "react";

/**
 * Horizontal paging for a scroll container.
 * Returns a ref to attach and a `scrollByPage` handler — no render state,
 * so the row re-renders only when its data changes.
 */
export function useRowScroll() {
  const ref = useRef<HTMLDivElement>(null);

  const scrollByPage = (direction: "left" | "right") => {
    const el = ref.current;
    if (!el) return;
    const amount = el.clientWidth * 0.9;
    el.scrollBy({ left: direction === "left" ? -amount : amount, behavior: "smooth" });
  };

  return { ref, scrollByPage };
}
