import type { DiscoveryIntent, RankedSeries } from "@/lib/types";
import { CoverArt } from "./CoverArt";
import { ReasonBadge, GenreChip } from "./Badges";
import { IntentChips } from "./IntentChips";

/** Grid of conversational-discovery results with the parsed intent up top. */
export function DiscoveryResults({
  query,
  intent,
  results,
  loading,
  error,
  onOpen,
}: {
  query: string;
  intent: DiscoveryIntent | null;
  results: RankedSeries[];
  loading: boolean;
  error: string | null;
  onOpen: (ranked: RankedSeries) => void;
}) {
  return (
    <section className="animate-fade-up">
      <p className="text-sm text-muted">Results for</p>
      <h2 className="mb-3 text-xl font-semibold text-foreground">&ldquo;{query}&rdquo;</h2>
      {intent && (
        <div className="mb-5">
          <IntentChips intent={intent} />
        </div>
      )}
      {loading && <p className="text-sm text-muted">Searching the catalog…</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}
      {!loading && !error && results.length === 0 && (
        <p className="text-sm text-muted">No matches — try loosening the constraints.</p>
      )}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {results.map((r) => (
          <button
            key={r.series.id}
            onClick={() => onOpen(r)}
            className="group text-left transition-transform duration-200 hover:-translate-y-1"
          >
            <CoverArt series={r.series} className="aspect-[3/4] w-full ring-1 ring-white/5" />
            <div className="mt-2 flex flex-wrap gap-1">
              {r.series.genres.slice(0, 2).map((g) => (
                <GenreChip key={g} genre={g} />
              ))}
            </div>
            <ReasonBadge reason={r.reason} />
          </button>
        ))}
      </div>
    </section>
  );
}
