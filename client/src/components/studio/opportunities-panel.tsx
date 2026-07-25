"use client";

import { Loader } from "@/components/motion/loader";
import { useCreatorOpportunities } from "@/hooks/api/use-creator";
import {
  arr,
  asRec,
  num,
  pct,
  str,
  Card,
  EmptyState,
  Pill,
  ProvenanceNote,
  SectionTitle,
} from "./ui";

/** GET /creator/opportunities — what to write next, split write-more / write-better. */
export function OpportunitiesPanel() {
  const { data, isLoading, isError, error } = useCreatorOpportunities();

  if (isLoading) return <PanelLoader />;
  if (isError || !data) {
    return (
      <EmptyState
        title="No demand report yet"
        hint={
          error instanceof Error
            ? error.message
            : "Run the pipeline (Admin → Pipeline) or GET /insights/demand?refresh=true."
        }
      />
    );
  }

  const d = asRec(data);
  const writeMore = arr(d.write_more).map(asRec);
  const writeBetter = arr(d.write_better).map(asRec);
  const avoid = arr(d.avoid_patterns).map(asRec);
  const segments = arr(d.your_segments).map((s) => str(s));

  return (
    <div className="space-y-6">
      <ProvenanceNote provenance={d.provenance} notice={d.data_notice} />

      {segments.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted-foreground">You publish in:</span>
          {segments.map((s) => (
            <Pill key={s}>{s}</Pill>
          ))}
        </div>
      ) : null}

      <section>
        <SectionTitle title="Write more" subtitle="Demand outruns supply — the audience is under-served." />
        {writeMore.length ? (
          <div className="grid gap-3 md:grid-cols-2">
            {writeMore.map((row, i) => (
              <OppCard key={i} row={row} kind="more" />
            ))}
          </div>
        ) : (
          <EmptyState title="No under-served segments found." />
        )}
      </section>

      <section>
        <SectionTitle title="Write better" subtitle="Demand is met, but high drop-off means execution is losing people." />
        {writeBetter.length ? (
          <div className="grid gap-3 md:grid-cols-2">
            {writeBetter.map((row, i) => (
              <OppCard key={i} row={row} kind="better" />
            ))}
          </div>
        ) : (
          <EmptyState title="Nothing flagged for re-execution." />
        )}
      </section>

      {avoid.length ? (
        <section>
          <SectionTitle title="Saturated — avoid" subtitle="Over-supplied patterns with weak retention." />
          <div className="flex flex-wrap gap-2">
            {avoid.map((row, i) => (
              <Pill key={i} tone="bad">
                {str(row.pattern)} · {pct(row.avg_completion_rate)} completion
              </Pill>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function OppCard({ row, kind }: { row: Record<string, unknown>; kind: "more" | "better" }) {
  const ratio = row.demand_vs_supply;
  return (
    <Card>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-foreground">{str(row.segment)}</p>
          <p className="mt-0.5 text-sm text-muted-foreground">{str(row.verdict)}</p>
        </div>
        {row.you_already_publish_here ? <Pill tone="good">yours</Pill> : null}
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
        <Fact label="Demand/supply" value={ratio != null ? `${num(ratio)}×` : "—"} />
        <Fact label="Completion" value={pct(row.completion_rate)} />
        <Fact label="Drop-off" value={pct(row.drop_off_rate)} />
        <Fact label="Listeners" value={String(num(row.unique_listeners))} />
        <Fact label="Plays" value={String(num(row.plays))} />
        <Fact
          label="Unmet search"
          value={String(num(row.searches_with_no_results))}
        />
      </div>
      <div className="mt-3 flex items-center gap-2">
        <Pill tone={kind === "more" ? "good" : "warn"}>
          opportunity {num(row.opportunity_score).toFixed(2)}
        </Pill>
        <Pill>confidence: {str(row.confidence, "low")}</Pill>
      </div>
    </Card>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-muted-foreground">{label}</p>
      <p className="font-semibold tabular-nums text-foreground">{value}</p>
    </div>
  );
}

function PanelLoader() {
  return (
    <div className="flex items-center gap-3 py-10 text-muted-foreground">
      <Loader variant="bars" size={28} />
      <span className="text-sm">Loading demand intelligence…</span>
    </div>
  );
}
