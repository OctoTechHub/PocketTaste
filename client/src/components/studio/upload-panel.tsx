"use client";

import { useState } from "react";

import { Input } from "@/components/motion/input";
import { Button, StatefulButton, type ButtonState } from "@/components/motion/button";
import { useUploadContent } from "@/hooks/api/use-catalog";
import { useSimilarityCheck } from "@/hooks/api/use-creator";
import { ApiError } from "@/lib/api/client";
import type { ContentCreate } from "@/lib/api/types";
import { arr, asRec, num, str, Card, Meter, Pill, SectionTitle } from "./ui";

const RISK_TONE = { clear: "good", review: "warn", block: "bad" } as const;

/** The six signals the gate reports, in the order a reviewer reads them. */
const SIGNAL_LABEL: Record<string, string> = {
  narrative_arc: "Story skeleton",
  semantic: "Meaning",
  lexical_shingle: "Verbatim",
  title: "Title",
  description: "Blurb",
  chapter_structure: "Chapters",
};

/** Upload a story with a pre-upload duplicate-screening step. */
export function UploadPanel() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [transcript, setTranscript] = useState("");
  const [genres, setGenres] = useState("");
  const [language, setLanguage] = useState("en");
  const [duration, setDuration] = useState("1800");

  const screen = useSimilarityCheck();
  const upload = useUploadContent();

  const body = (): ContentCreate => ({
    title,
    description,
    transcript,
    language,
    genres: genres.split(",").map((g) => g.trim()).filter(Boolean),
    duration_seconds: Number(duration) || 1800,
  });

  const uploadState: ButtonState = upload.isPending
    ? "loading"
    : upload.isError
      ? "error"
      : upload.isSuccess
        ? "success"
        : "idle";

  // POST /similarity/check returns a SimilarityReport: `risk`, `top_score`,
  // `originality_score`, `matches`, `explanation`. A rejected upload (409) carries
  // the same shape under `error.details`, so a block shows up here too rather than
  // only as a one-line form error.
  const blockDetails = asRec(
    upload.error instanceof ApiError && upload.error.status === 409 ? upload.error.details : null,
  );
  // Both a manual screen and a rejected upload produce a report. Show whichever the
  // creator ran last, so a re-screen after a block isn't hidden behind the stale one.
  const showBlock = Boolean(blockDetails.risk) && upload.submittedAt > screen.submittedAt;
  const report = showBlock ? blockDetails : asRec(screen.data);
  const hasReport = showBlock || Boolean(screen.data);
  const verdict = str(report.risk) as keyof typeof RISK_TONE;
  const originality = num(report.originality_score, 1 - num(report.top_score));
  const matches = arr(report.matches).map(asRec);

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <Card>
        <SectionTitle title="Upload a story" subtitle="Screened for duplication before it’s stored." />
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            upload.mutate({ body: body() });
          }}
        >
          <Input label="Title" value={title} onChange={setTitle} placeholder="Story title" required />
          <div>
            <label className="px-1 text-sm font-medium text-foreground">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="A short blurb (min 10 chars)…"
              className="mt-1.5 w-full rounded-2xl border border-border bg-transparent px-4 py-3 text-sm text-foreground outline-none placeholder:text-muted-foreground/60 focus:border-foreground/40"
            />
          </div>
          <div>
            <label className="px-1 text-sm font-medium text-foreground">Transcript</label>
            <textarea
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              rows={6}
              placeholder="Full transcript (min 20 chars)…"
              className="mt-1.5 w-full rounded-2xl border border-border bg-transparent px-4 py-3 text-sm text-foreground outline-none placeholder:text-muted-foreground/60 focus:border-foreground/40"
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <Input label="Genres" value={genres} onChange={setGenres} placeholder="horror, thriller" />
            <Input label="Language" value={language} onChange={setLanguage} placeholder="en" />
            <Input label="Duration (s)" value={duration} onChange={setDuration} inputMode="numeric" />
          </div>

          <div className="flex gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => screen.mutate({ title, description, transcript, language, genres: body().genres })}
              disabled={screen.isPending || title.length < 2}
            >
              {screen.isPending ? "Screening…" : "Screen for duplicates"}
            </Button>
            <StatefulButton
              type="submit"
              state={uploadState}
              disabled={title.length < 2 || transcript.length < 20}
              loadingText="Uploading"
              successText="Published"
              errorText="Failed"
            >
              Upload
            </StatefulButton>
          </div>

          {upload.isError ? (
            <p className="text-sm text-destructive">
              {upload.error instanceof ApiError && upload.error.status === 409
                ? "This is too similar to an existing story — try a more original angle."
                : "Couldn’t publish just yet. Please try again."}
            </p>
          ) : null}
          {upload.isSuccess ? (
            <p className="text-sm text-success">Published! It’s now in your catalog.</p>
          ) : null}
        </form>
      </Card>

      <div className="space-y-3">
        <SectionTitle title="Originality check" subtitle="How your draft compares to the catalog." />
        {screen.isPending ? (
          <Card className="text-sm text-muted-foreground">Checking your draft…</Card>
        ) : hasReport ? (
          <Card className="space-y-3">
            <div className="flex items-center gap-2">
              <Pill tone={RISK_TONE[verdict] ?? "neutral"}>{VERDICT_LABEL[verdict] ?? "Reviewed"}</Pill>
              <span className="ml-auto text-sm tabular-nums text-muted-foreground">
                {Math.round(originality * 100)}% original
              </span>
            </div>
            <p className="text-sm text-muted-foreground">{VERDICT_HINT[verdict] ?? ""}</p>
            {str(report.explanation) ? (
              <p className="text-sm text-foreground/80">{str(report.explanation)}</p>
            ) : null}

            {matches.length ? (
              <div className="space-y-3 border-t border-border pt-3">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Closest in the catalog
                </p>
                {matches.slice(0, 3).map((match, index) => (
                  <MatchRow key={str(match.content_id) || index} match={match} />
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                Nothing in the catalog was close enough to compare against.
              </p>
            )}
            {/* Absent on the 409 payload, which ships only the top three matches. */}
            {num(report.candidates_compared) > 0 ? (
              <p className="text-xs text-muted-foreground">
                Compared against {num(report.candidates_compared)} catalog items.
              </p>
            ) : null}
          </Card>
        ) : (
          <Card className="text-sm text-muted-foreground">
            Run the originality check to see how your draft compares before publishing.
          </Card>
        )}
      </div>
    </div>
  );
}

/** One catalog neighbour with the per-signal breakdown that produced its score.
 *  The blend alone is not reviewable — a creator needs to see *which* signal fired. */
function MatchRow({ match }: { match: Record<string, unknown> }) {
  const signals = asRec(match.signals);
  const kind = str(match.duplicate_kind);
  return (
    <div className="space-y-2">
      <div className="flex items-baseline gap-2">
        <span className="truncate text-sm font-medium text-foreground">{str(match.title)}</span>
        <span className="ml-auto shrink-0 text-sm tabular-nums text-muted-foreground">
          {Math.round(num(match.combined_score) * 100)}%
        </span>
      </div>
      <Meter value={num(match.combined_score)} tone={num(match.combined_score) >= 0.72 ? "warn" : "primary"} />
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
        {Object.entries(SIGNAL_LABEL)
          .filter(([key]) => num(signals[key]) > 0)
          .map(([key, label]) => (
            <span key={key} className="tabular-nums">
              {label} {num(signals[key]).toFixed(2)}
            </span>
          ))}
      </div>
      {kind && kind !== "none" ? (
        <Pill tone="bad">{kind.replace(/_/g, " ")}</Pill>
      ) : null}
      {str(match.rationale) ? (
        <p className="text-xs text-muted-foreground">{str(match.rationale)}</p>
      ) : null}
    </div>
  );
}

const VERDICT_LABEL: Record<string, string> = {
  clear: "Original",
  review: "Worth a second look",
  block: "Too similar",
};

const VERDICT_HINT: Record<string, string> = {
  clear: "Looks fresh — nothing close in the catalog.",
  review: "Some overlap with existing stories. You can still publish it.",
  block: "Very close to something already published. Consider a new angle.",
};
