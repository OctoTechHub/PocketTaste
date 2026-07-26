"use client";

import { useState } from "react";
import { FileText } from "lucide-react";

import { Loader } from "@/components/motion/loader";
import { useTranscript } from "@/hooks/api/use-catalog";

/** Collapsible transcript for a story — GET /catalog/{id}/transcript, fetched on open. */
export function TranscriptSection({ contentId }: { contentId: string }) {
  const [open, setOpen] = useState(false);
  const { data, isLoading, isError } = useTranscript(contentId, open);

  return (
    <div className="mt-4 rounded-xl border border-border bg-muted/40">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm font-medium text-foreground"
      >
        <FileText className="h-4 w-4 text-muted-foreground" />
        Transcript
        <span className="ml-auto text-xs text-muted-foreground">{open ? "hide" : "show"}</span>
      </button>
      {open ? (
        <div className="border-t border-border px-4 py-3">
          {isLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader variant="dots" size={14} /> Loading transcript…
            </div>
          ) : isError ? (
            <p className="text-sm text-muted-foreground">
              No transcript for this story yet.
            </p>
          ) : (
            <p className="max-h-80 overflow-auto whitespace-pre-wrap text-sm leading-relaxed text-foreground/80">
              {String((data as { transcript?: string })?.transcript ?? "No transcript.")}
            </p>
          )}
        </div>
      ) : null}
    </div>
  );
}
