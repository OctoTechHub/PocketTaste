"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Loader } from "@/components/motion/loader";
import { JsonBlock } from "@/components/studio/ui";

/**
 * A lazily-fetched "describe" endpoint, rendered as an expandable JSON card.
 * Fires the request only when opened, so a grid of these stays cheap.
 */
export function ReferenceCard({
  label,
  path,
  queryKey,
  fetcher,
}: {
  label: string;
  path: string;
  queryKey: readonly unknown[];
  fetcher: () => Promise<unknown>;
}) {
  const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey, queryFn: fetcher, enabled: open, staleTime: 300_000 });

  return (
    <div className="rounded-xl border border-border bg-card">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
      >
        <div>
          <p className="text-sm font-medium text-foreground">{label}</p>
          <p className="font-mono text-[11px] text-muted-foreground">{path}</p>
        </div>
        <span className="text-xs text-muted-foreground">{open ? "hide" : "fetch"}</span>
      </button>
      {open ? (
        <div className="border-t border-border p-3">
          {q.isLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader variant="dots" size={14} /> Loading…
            </div>
          ) : q.isError ? (
            <p className="text-sm text-destructive">
              {q.error instanceof Error ? q.error.message : "Request failed."}
            </p>
          ) : (
            <JsonBlock data={q.data} label="Response" />
          )}
        </div>
      ) : null}
    </div>
  );
}
