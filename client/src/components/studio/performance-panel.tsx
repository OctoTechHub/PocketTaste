"use client";

import { ChevronDown } from "lucide-react";
import { useState } from "react";

import { Loader } from "@/components/motion/loader";
import { useCreatorPerformance } from "@/hooks/api/use-creator";
import { ContentAnalytics } from "./content-analytics";
import {
  arr,
  asRec,
  num,
  pct,
  str,
  Card,
  EmptyState,
  Meter,
  Pill,
  StatTile,
} from "./ui";

/** GET /creator/performance — per-story retention, each expandable to full analytics. */
export function PerformancePanel() {
  const { data, isLoading, isError, error } = useCreatorPerformance();
  const [open, setOpen] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="flex items-center gap-3 py-10 text-muted-foreground">
        <Loader variant="bars" size={28} />
        <span className="text-sm">Loading your stories…</span>
      </div>
    );
  }
  if (isError || !data) {
    return (
      <EmptyState
        title="Couldn’t load performance"
        hint={error instanceof Error ? error.message : undefined}
      />
    );
  }

  const d = asRec(data);
  const stories = arr(d.stories).map(asRec);

  if (num(d.catalog_items) === 0) {
    return (
      <EmptyState
        title="You haven’t published anything yet"
        hint="Use the Upload tab to add your first story."
      />
    );
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Stories" value={num(d.catalog_items)} />
        <StatTile label="With listeners" value={num(d.items_with_listeners)} />
        <StatTile label="Total listeners" value={num(d.total_listeners)} />
        <StatTile
          label="Avg completion"
          value={Math.round(num(d.avg_completion_rate) * 100)}
          suffix="%"
        />
      </div>

      <div className="space-y-3">
        {stories.map((s) => {
          const id = str(s.content_id);
          const isOpen = open === id;
          const conf = str(s.confidence, "no_data");
          return (
            <Card key={id} className="p-0">
              <button
                type="button"
                onClick={() => setOpen(isOpen ? null : id)}
                className="flex w-full items-center gap-4 p-4 text-left"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="truncate font-semibold text-foreground">{str(s.title)}</p>
                    <Pill>{str(s.segment)}</Pill>
                    {s.duplicate_flag ? <Pill tone="bad">{str(s.duplicate_flag)}</Pill> : null}
                  </div>
                  <div className="mt-2 grid grid-cols-3 gap-3 text-xs text-muted-foreground sm:grid-cols-4">
                    <span>{num(s.listeners)} listeners</span>
                    <span>completion {pct(s.completion_rate)}</span>
                    <span>drop-off {pct(s.drop_off_rate)}</span>
                    <Pill tone={conf === "high" ? "good" : conf === "no_data" ? "bad" : "warn"}>
                      {conf}
                    </Pill>
                  </div>
                  <div className="mt-2 max-w-sm">
                    <Meter value={num(s.completion_rate)} />
                  </div>
                </div>
                <ChevronDown
                  className={`h-5 w-5 shrink-0 text-muted-foreground transition-transform ${
                    isOpen ? "rotate-180" : ""
                  }`}
                />
              </button>
              {isOpen ? (
                <div className="border-t border-white/10 px-4 pb-4">
                  <ContentAnalytics contentId={id} />
                </div>
              ) : null}
            </Card>
          );
        })}
      </div>

      {str(d.note) ? <p className="text-xs text-muted-foreground">{str(d.note)}</p> : null}
    </div>
  );
}
