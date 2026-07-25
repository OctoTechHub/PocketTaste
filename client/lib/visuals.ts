// Deterministic cover-art gradients + genre color system (no external images).

export const GENRE_COLOR: Record<string, string> = {
  romance: "#ff5ca8",
  thriller: "#7c5cff",
  horror: "#d1495b",
  mythology: "#f0a500",
  scifi: "#22d3ee",
  comedy: "#f7b32b",
  drama: "#a78bfa",
  crime: "#ef4444",
  fantasy: "#34d399",
  "slice-of-life": "#60a5fa",
};

export function genreColor(genre: string): string {
  return GENRE_COLOR[genre] ?? "#7c5cff";
}

function hash(str: string): number {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** Stable diagonal gradient derived from the series' primary genre + id. */
export function coverGradient(id: string, genres: string[]): string {
  const base = genreColor(genres[0] ?? "");
  const angle = hash(id) % 360;
  const second = genreColor(genres[1] ?? genres[0] ?? "");
  return `linear-gradient(${angle}deg, ${base} 0%, ${second}88 55%, #0a0a12 130%)`;
}

export function initials(title: string): string {
  return title
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}
