"use client";

import { useEffect } from "react";
import type { RankedSeries } from "@/lib/types";
import { useSeriesDetail } from "@/features/series/useSeriesDetail";
import { CoverArt } from "./CoverArt";
import { GenreChip, Chip, SourceTag } from "./Badges";
import { ScoreBreakdownBars } from "./ScoreBreakdownBars";
import { SimulateBar } from "./SimulateBar";

/** Detail view: synopsis, transparent score breakdown, simulate actions, and
 * "more like this" (which re-opens the modal for the chosen neighbour). */
export function SeriesModal({
  ranked,
  userId,
  onClose,
  onOpen,
  onLogged,
}: {
  ranked: RankedSeries;
  userId: string | null;
  onClose: () => void;
  onOpen: (ranked: RankedSeries) => void;
  onLogged: () => void;
}) {
  const { series, breakdown, reason, sources } = ranked;
  const { data } = useSeriesDetail(series.id);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 p-4 backdrop-blur-sm sm:p-8"
      onClick={onClose}
    >
      <div
        className="animate-fade-up my-auto w-full max-w-3xl rounded-2xl border border-border bg-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex gap-5 p-6">
          <CoverArt series={series} showMeta={false} className="h-56 w-40 shrink-0 ring-1 ring-white/10" />
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-2xl font-bold text-foreground">{series.title}</h2>
              <button onClick={onClose} className="text-muted hover:text-foreground" aria-label="Close">
                ✕
              </button>
            </div>
            <p className="mt-1 text-xs text-muted">
              {series.language} · {series.episodeCount} episodes · ~{series.avgEpisodeMinutes} min ·{" "}
              {series.pacing} · {series.coinPriceApprox} coins
              {series.isOriginal && " · PocketFM Original"}
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {series.genres.map((g) => (
                <GenreChip key={g} genre={g} />
              ))}
              {series.tone.map((t) => (
                <Chip key={t} color="#a78bfa">
                  {t}
                </Chip>
              ))}
            </div>
            <p className="mt-3 text-sm leading-relaxed text-foreground/90">{series.synopsis}</p>
            {reason && (
              <div className="mt-3 rounded-lg border border-accent/30 bg-accent/10 p-3">
                <p className="text-xs uppercase tracking-wide text-accent">Why this, for you</p>
                <p className="mt-1 text-sm text-foreground">{reason}</p>
                <div className="mt-2 flex gap-1">
                  {sources.map((s) => (
                    <SourceTag key={s} source={s} />
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="grid gap-6 border-t border-border p-6 sm:grid-cols-2">
          <div>
            <p className="mb-3 text-xs uppercase tracking-wide text-muted">Ranking breakdown</p>
            <ScoreBreakdownBars breakdown={breakdown} />
          </div>
          <div className="space-y-5">
            {userId && <SimulateBar userId={userId} series={series} onLogged={onLogged} />}
            <div>
              <p className="mb-2 text-xs uppercase tracking-wide text-muted">More like this</p>
              <div className="no-scrollbar flex gap-3 overflow-x-auto">
                {data?.similar.slice(0, 6).map((r) => (
                  <button
                    key={r.series.id}
                    onClick={() => onOpen(r)}
                    className="w-20 shrink-0 text-left transition hover:-translate-y-0.5"
                  >
                    <CoverArt series={r.series} showMeta={false} className="aspect-[3/4] w-20 ring-1 ring-white/5" />
                    <p className="mt-1 line-clamp-2 text-[11px] text-muted">{r.series.title}</p>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
