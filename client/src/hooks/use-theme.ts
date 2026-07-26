"use client";

import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";
export const THEME_KEY = "bolsillo.theme";

/**
 * Reads/toggles the app theme. The `dark` class on <html> is what flips the
 * palette (see globals.css); this hook keeps that class + localStorage in sync.
 * The initial class is set pre-hydration by the inline script in the layout, so
 * there's no flash — this hook just mirrors and mutates it.
 */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    setTheme(document.documentElement.classList.contains("dark") ? "dark" : "light");
  }, []);

  const apply = useCallback((next: Theme) => {
    document.documentElement.classList.toggle("dark", next === "dark");
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* private mode — theme just won't persist */
    }
    setTheme(next);
  }, []);

  const toggle = useCallback(() => {
    apply(document.documentElement.classList.contains("dark") ? "light" : "dark");
  }, [apply]);

  return { theme, toggle, setTheme: apply };
}
