"use client";

import { PenLine } from "lucide-react";

import { Loader } from "@/components/motion/loader";
import { useCreatorOpportunities } from "@/hooks/api/use-creator";
import type { CopilotSeed } from "./studio-shell";
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

type WriteThisSeed = Omit<CopilotSeed, "seedId">;

/** GET /creator/opportunities — what to write next, split write-more / write-better. */
export function OpportunitiesPanel({
  onWriteThis,
}: {
  /** Sends a segment to the Copilot tab, prefilled, and switches to it. */
  onWriteThis: (seed: WriteThisSeed) => void;
}) {
  const { data, isLoading, isError } = useCreatorOpportunities();

  if (isLoading) return <PanelLoader />;
  if (isError || !data) {
    return (
      <EmptyState
        title="Gathering your opportunities"
        hint="We’re still learning what your audience wants. Check back once there’s a little more listening activity."
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
              <OppCard key={i} row={row} kind="more" onWriteThis={onWriteThis} />
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
              <OppCard key={i} row={row} kind="better" onWriteThis={onWriteThis} />
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

function OppCard({
  row,
  kind,
  onWriteThis,
}: {
  row: Record<string, unknown>;
  kind: "more" | "better";
  onWriteThis: (seed: WriteThisSeed) => void;
}) {
  const ratio = row.demand_vs_supply;
  const segment = str(row.segment);
  const [genre, language] = segment.split("/");

  return (
    <Card className="cursor-pointer transition-colors hover:border-primary/40 hover:bg-muted">
      <button
        type="button"
        onClick={() =>
          onWriteThis({
            premise: `A ${genre || "story"} audio series in ${
              language === "en" ? "English" : language || "English"
            }. ${str(row.verdict)}`,
            genre: genre || "fantasy",
            language: language || "en",
            workingTitle: "",
          })
        }
        className="block w-full text-left"
      >
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="font-semibold text-foreground">{segment}</p>
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
        <div className="mt-3 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Pill tone={kind === "more" ? "good" : "warn"}>
              opportunity {num(row.opportunity_score).toFixed(2)}
            </Pill>
            <Pill>confidence: {str(row.confidence, "low")}</Pill>
          </div>
          <span className="inline-flex items-center gap-1 text-xs font-medium text-primary">
            <PenLine className="h-3.5 w-3.5" /> Write this
          </span>
        </div>
      </button>
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
