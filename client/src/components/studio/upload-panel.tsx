"use client";

import { useState } from "react";

import { Input } from "@/components/motion/input";
import { Button, StatefulButton, type ButtonState } from "@/components/motion/button";
import { useUploadContent } from "@/hooks/api/use-catalog";
import { useSimilarityCheck } from "@/hooks/api/use-creator";
import { ApiError } from "@/lib/api/client";
import type { ContentCreate } from "@/lib/api/types";
import { asRec, num, str, Card, JsonBlock, Pill, SectionTitle } from "./ui";

const RISK_TONE = { clear: "good", review: "warn", block: "bad" } as const;

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

  const report = asRec(screen.data);
  const verdict = str(report.risk_level ?? report.verdict) as keyof typeof RISK_TONE;

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
              {upload.error instanceof ApiError ? upload.error.message : "Upload failed."}
              {upload.error instanceof ApiError && upload.error.status === 409
                ? " — blocked by the similarity gate."
                : ""}
            </p>
          ) : null}
          {upload.isSuccess ? (
            <p className="text-sm text-emerald-400">
              Uploaded as {str(asRec(upload.data).content_id)}.
            </p>
          ) : null}
        </form>
      </Card>

      <div className="space-y-3">
        <SectionTitle title="Screening report" subtitle="POST /similarity/check" />
        {screen.isPending ? (
          <Card>Screening the draft…</Card>
        ) : screen.data ? (
          <Card className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Verdict</span>
              <Pill tone={RISK_TONE[verdict] ?? "neutral"}>{verdict || "—"}</Pill>
              <span className="ml-auto text-sm tabular-nums text-muted-foreground">
                score {num(report.combined_score ?? report.score).toFixed(2)}
              </span>
            </div>
            <JsonBlock data={screen.data} label="Signal breakdown" />
          </Card>
        ) : (
          <Card className="text-sm text-muted-foreground">
            Run “Screen for duplicates” to check your draft against the catalog before uploading.
          </Card>
        )}
      </div>
    </div>
  );
}
