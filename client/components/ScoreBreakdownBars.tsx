import type { ScoreBreakdown } from "@/lib/types";

const FEATURES: { key: keyof ScoreBreakdown; label: string }[] = [
  { key: "contentSimilarity", label: "Taste match" },
  { key: "genreAffinity", label: "Genre affinity" },
  { key: "languageMatch", label: "Language" },
  { key: "toneMatch", label: "Tone" },
  { key: "pacingMatch", label: "Pacing" },
  { key: "lengthFit", label: "Episode length fit" },
  { key: "monetizationProxy", label: "Coin-unlock likelihood" },
  { key: "freshness", label: "Freshness" },
];

/** Transparent, per-feature view of why a series scored the way it did. */
export function ScoreBreakdownBars({ breakdown }: { breakdown: ScoreBreakdown }) {
  return (
    <div className="space-y-2">
      {FEATURES.map(({ key, label }) => {
        const v = breakdown[key];
        return (
          <div key={key} className="flex items-center gap-3">
            <span className="w-40 shrink-0 text-xs text-muted">{label}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/5">
              <div
                className="h-full rounded-full bg-gradient-to-r from-accent to-accent-2"
                style={{ width: `${Math.round(v * 100)}%` }}
              />
            </div>
            <span className="w-8 text-right text-[11px] font-mono text-muted">
              {Math.round(v * 100)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
