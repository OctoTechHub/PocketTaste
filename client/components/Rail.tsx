import type { FeedRail } from "@/lib/types";
import { SeriesCard } from "./SeriesCard";

/** A themed horizontal row of recommendations. */
export function Rail({
  rail,
  onOpen,
}: {
  rail: FeedRail;
  onOpen: (ranked: import("@/lib/types").RankedSeries) => void;
}) {
  if (rail.items.length === 0) return null;
  return (
    <section className="animate-fade-up">
      <div className="mb-3 flex items-baseline gap-3">
        <h2 className="text-lg font-semibold text-foreground">{rail.title}</h2>
        {rail.subtitle && <p className="text-xs text-muted">{rail.subtitle}</p>}
      </div>
      <div className="no-scrollbar flex gap-4 overflow-x-auto pb-2">
        {rail.items.map((item) => (
          <SeriesCard key={item.series.id} ranked={item} onOpen={onOpen} />
        ))}
      </div>
    </section>
  );
}
