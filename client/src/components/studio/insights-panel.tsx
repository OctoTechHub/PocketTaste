"use client";

import { Loader } from "@/components/motion/loader";
import { useBriefs, useDemand, useSaturation } from "@/hooks/api/use-creator";
import { DemandChart, DemandTrendChart, SaturationChart } from "./insights-charts";
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

/** Platform demand, saturation and evidence-backed briefs. */
export function InsightsPanel() {
  const demand = useDemand();
  const saturation = useSaturation();
  const briefs = useBriefs();

  if (demand.isLoading) {
    return (
      <div className="flex items-center gap-3 py-10 text-muted-foreground">
        <Loader variant="bars" size={28} />
        <span className="text-sm">Loading demand report…</span>
      </div>
    );
  }
  if (demand.isError) {
    return (
      <EmptyState
        title="Audience insights are on the way"
        hint="Once there’s enough listening across the catalog, demand and saturation land here."
      />
    );
  }

  const d = asRec(demand.data);
  const segments = arr(d.segments).map(asRec);
  const patterns = arr(asRec(saturation.data).patterns).map(asRec);
  const briefList = arr(asRec(briefs.data).briefs).map(asRec);

  return (
    <div className="space-y-6">
      <ProvenanceNote provenance={d.provenance} notice={d.data_notice} />

      <section>
        <SectionTitle title="Demand by segment" subtitle="Where your audience is — top segments by listeners." />
        {segments.length ? (
          <Card className="mb-4">
            <DemandChart segments={segments} />
          </Card>
        ) : null}
        {segments.length ? (
          <div className="overflow-x-auto rounded-xl border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">Segment</th>
                  <th className="px-3 py-2">Opportunity</th>
                  <th className="px-3 py-2">Completion</th>
                  <th className="px-3 py-2">Drop-off</th>
                  <th className="px-3 py-2">Listeners</th>
                </tr>
              </thead>
              <tbody>
                {segments.slice(0, 20).map((row, i) => (
                  <tr key={i} className="border-t border-border/60">
                    <td className="px-3 py-2 font-medium text-foreground">{str(row.segment)}</td>
                    <td className="px-3 py-2 tabular-nums">{num(row.opportunity_score).toFixed(2)}</td>
                    <td className="px-3 py-2 tabular-nums">{pct(row.completion_rate)}</td>
                    <td className="px-3 py-2 tabular-nums">{pct(row.drop_off_rate)}</td>
                    <td className="px-3 py-2 tabular-nums">{num(row.unique_listeners)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No segments measured yet." />
        )}
      </section>

      <section>
        <SectionTitle
          title="Completion vs drop-off"
          subtitle="How well each top segment holds its audience."
        />
        {segments.length ? (
          <Card>
            <DemandTrendChart segments={segments} />
          </Card>
        ) : (
          <EmptyState title="No retention data yet." />
        )}
      </section>

      <section>
        <SectionTitle title="Saturated patterns" subtitle="Over-supplied relative to how well they retain." />
        {patterns.length ? (
          <Card className="mb-4">
            <SaturationChart patterns={patterns} />
          </Card>
        ) : null}
        {patterns.length ? (
          <div className="flex flex-wrap gap-2">
            {patterns.map((p, i) => (
              <Pill key={i} tone="bad">
                {str(p.narrative_pattern ?? p.pattern)} · sat {num(p.saturation_index).toFixed(2)}
              </Pill>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            {saturation.isLoading ? "Loading…" : "None."}
          </p>
        )}
      </section>

      <section>
        <SectionTitle title="Content briefs" subtitle="Evidence-backed, grounded in the metrics above." />
        {briefList.length ? (
          <div className="grid gap-3 md:grid-cols-2">
            {briefList.map((b, i) => (
              <Card key={i}>
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold text-foreground">{str(b.title ?? b.segment)}</p>
                  <Pill tone="good">AI brief</Pill>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  {str(b.premise ?? b.rationale ?? b.summary)}
                </p>
              </Card>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            {briefs.isLoading ? "Loading…" : "No briefs generated yet."}
          </p>
        )}
      </section>
    </div>
  );
}
