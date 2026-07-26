"use client";

import { Loader } from "@/components/motion/loader";
import { useContentDropOff } from "@/hooks/api/use-analytics";
import { arr, asRec, num, pct, str, Card, Meter, Pill } from "./ui";

/** Retention curve + plain-English drop-off diagnosis for one story. */
export function ContentAnalytics({ contentId }: { contentId: string }) {
  const { data, isLoading, isError } = useContentDropOff(contentId);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
        <Loader variant="dots" size={16} /> Loading retention…
      </div>
    );
  }
  if (isError || !data) {
    return (
      <p className="py-3 text-sm text-muted-foreground">
        Detailed retention for this story will appear once it has some listens.
      </p>
    );
  }

  const d = asRec(data);
  const curve = arr(d.retention_curve).map(asRec);
  const weakest = asRec(d.weakest_chapter);
  const confidence = str(d.confidence, "no_data");

  return (
    <div className="mt-3 space-y-4">
      <p className="text-sm text-foreground/90">{str(d.explanation)}</p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Completion" value={pct(d.completion_rate)} />
        <Metric label="Drop-off" value={pct(d.drop_off_rate)} />
        <Metric
          label="Median abandon"
          value={d.median_abandon_seconds != null ? `${Math.round(num(d.median_abandon_seconds))}s` : "—"}
        />
        <Metric label="Sample" value={String(num(d.sample_size))} />
      </div>

      {curve.length > 0 ? (
        <div>
          <p className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
            Retention curve
          </p>
          <div className="flex items-end gap-0.5" style={{ height: 64 }}>
            {curve.map((point, i) => {
              const retained = num(point.retained ?? point.retention ?? point.share, 0);
              return (
                <span
                  key={i}
                  title={`${Math.round(retained * 100)}%`}
                  className="flex-1 rounded-t bg-primary/70"
                  style={{ height: `${Math.max(2, retained * 100)}%` }}
                />
              );
            })}
          </div>
        </div>
      ) : null}

      {weakest.title || weakest.chapter_index != null ? (
        <Card className="bg-amber-500/[0.06] p-4">
          <p className="text-xs uppercase tracking-wide text-amber-300/80">Weakest chapter</p>
          <p className="mt-1 font-medium text-foreground">
            #{num(weakest.chapter_index)} · {str(weakest.title, "Untitled")}
          </p>
          <div className="mt-2">
            <Meter value={num(weakest.interest_score)} tone="warn" />
          </div>
        </Card>
      ) : null}

      <div className="flex items-center gap-2">
        <Pill tone={confidence === "high" ? "good" : confidence === "no_data" ? "bad" : "warn"}>
          {confidence === "no_data" ? "not enough data" : `${confidence} confidence`}
        </Pill>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-lg font-bold tabular-nums text-foreground">{value}</p>
    </div>
  );
}
