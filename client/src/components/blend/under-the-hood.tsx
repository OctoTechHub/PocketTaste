"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, Terminal } from "lucide-react";

import { cn } from "@/lib/utils";
import type { BlendStage } from "@/hooks/api/use-blend";

const STEP_LABEL: Record<string, string> = {
  members: "read profiles",
  candidates: "candidate pool",
  score: "rank",
  normalise: "normalise",
  combine: "aggregate",
  select: "select",
  done: "done",
};

/** Everything except the message and timing, rendered as `key=value`. */
function detailOf(stage: BlendStage): string {
  return Object.entries(stage)
    .filter(([key]) => !["type", "step", "message", "elapsed_ms"].includes(key))
    .map(([key, value]) =>
      typeof value === "object" && value !== null
        ? `${key}=${JSON.stringify(value)}`
        : `${key}=${String(value)}`,
    )
    .join("  ");
}

/**
 * The engine reporting on itself while it runs.
 *
 * Each line is emitted by the server as a stage finishes, carrying the counts it
 * actually worked with — candidates surviving the filter, items scored per listener,
 * slots the fairness pass had to reassign. The panel holds one fixed height whether
 * it is empty, filling or full, so the page never reflows as lines arrive.
 */
export function UnderTheHood({
  stages,
  isStreaming,
}: {
  stages: BlendStage[];
  isStreaming: boolean;
}) {
  const [open, setOpen] = useState(true);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = scroller.current;
    if (node && open) node.scrollTop = node.scrollHeight;
  }, [stages, open]);

  return (
    <section className="overflow-hidden rounded-2xl border border-border bg-card">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls="blend-log"
        className="flex min-h-11 w-full items-center gap-2.5 px-4 text-left transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <Terminal className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
        <span className="text-[11px] font-black uppercase tracking-[0.2em] text-muted-foreground">
          Under the hood
        </span>
        {isStreaming ? (
          <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <span
              className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary motion-reduce:animate-none"
              aria-hidden
            />
            running
          </span>
        ) : stages.length ? (
          <span className="text-[11px] tabular-nums text-muted-foreground">
            {stages[stages.length - 1]?.elapsed_ms}ms
          </span>
        ) : null}
        <ChevronDown
          className={cn(
            "ml-auto h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 motion-reduce:transition-none",
            open && "rotate-180",
          )}
          aria-hidden
        />
      </button>

      {open ? (
        <div
          id="blend-log"
          ref={scroller}
          role="log"
          aria-live="polite"
          aria-busy={isStreaming}
          className="h-[168px] overflow-y-auto border-t border-border px-4 py-2.5 font-mono text-[11px] leading-[1.7]"
        >
          {stages.length === 0 ? (
            <p className="text-muted-foreground">waiting for the server…</p>
          ) : (
            <ol className="space-y-0.5">
              {stages.map((stage, index) => (
                <li key={`${stage.step}-${index}`} className="flex gap-2.5">
                  <span className="w-12 shrink-0 text-right tabular-nums text-muted-foreground/60">
                    {stage.elapsed_ms}ms
                  </span>
                  <span
                    className={cn(
                      "w-[104px] shrink-0 truncate",
                      stage.step === "done" ? "text-primary" : "text-muted-foreground",
                    )}
                  >
                    {STEP_LABEL[stage.step] ?? stage.step}
                  </span>
                  <span className="min-w-0 flex-1 text-foreground/85">
                    {stage.message}
                    {detailOf(stage) ? (
                      <span className="block break-all text-muted-foreground/70">
                        {detailOf(stage)}
                      </span>
                    ) : null}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </div>
      ) : null}
    </section>
  );
}
