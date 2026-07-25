import type { Series } from "@/lib/types";
import { coverGradient, initials } from "@/lib/visuals";

/** Deterministic generated cover — no image assets needed. */
export function CoverArt({
  series,
  className = "",
  showMeta = true,
}: {
  series: Series;
  className?: string;
  showMeta?: boolean;
}) {
  return (
    <div
      className={`relative flex items-end overflow-hidden rounded-xl ${className}`}
      style={{ background: coverGradient(series.id, series.genres) }}
    >
      <span className="pointer-events-none absolute right-2 top-2 text-3xl font-black text-white/25">
        {initials(series.title)}
      </span>
      {series.isNew && (
        <span className="absolute left-2 top-2 rounded bg-black/40 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">
          New
        </span>
      )}
      {showMeta && (
        <div className="w-full bg-gradient-to-t from-black/70 to-transparent p-2.5">
          <p className="line-clamp-2 text-sm font-semibold leading-tight text-white">
            {series.title}
          </p>
          <p className="mt-0.5 text-[11px] text-white/70">
            {series.language} · {series.episodeCount} eps · {series.avgEpisodeMinutes}m
          </p>
        </div>
      )}
    </div>
  );
}
