import type { RankedSeries } from "@/lib/types";
import { CoverArt } from "./CoverArt";
import { ReasonBadge, SourceTag } from "./Badges";

/** A single recommendation in a rail. Presentational — click bubbles up via onOpen. */
export function SeriesCard({
  ranked,
  onOpen,
  showReason = true,
}: {
  ranked: RankedSeries;
  onOpen: (ranked: RankedSeries) => void;
  showReason?: boolean;
}) {
  const { series, sources, reason } = ranked;
  return (
    <button
      onClick={() => onOpen(ranked)}
      className="group w-44 shrink-0 text-left transition-transform duration-200 hover:-translate-y-1"
    >
      <CoverArt series={series} className="aspect-[3/4] w-44 shadow-lg shadow-black/40 ring-1 ring-white/5" />
      <div className="mt-2 flex flex-wrap items-center gap-1">
        {sources.slice(0, 2).map((s) => (
          <SourceTag key={s} source={s} />
        ))}
        <span className="ml-auto text-[11px] font-mono text-accent">
          {(ranked.score * 100).toFixed(0)}
        </span>
      </div>
      {showReason && <ReasonBadge reason={reason} />}
    </button>
  );
}
