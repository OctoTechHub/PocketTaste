export type Theme = "light" | "dark";

/**
 * Where the chosen theme is persisted. Lives here rather than in `use-theme`
 * because the root layout inlines it into a pre-hydration <script>: exports of a
 * `"use client"` module become client references on the server, so reading it
 * from there yields `undefined` at render time and the script silently no-ops.
 */
export const THEME_KEY = "bolsillo.theme";
