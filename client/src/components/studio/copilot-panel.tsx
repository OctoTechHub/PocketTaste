"use client";

import { useState } from "react";

import { Input } from "@/components/motion/input";
import { Button } from "@/components/motion/button";
import { Loader } from "@/components/motion/loader";
import { useCopilotDraft, useCopilotOutline } from "@/hooks/api/use-creator";
import type { StoryOutlineRequest } from "@/lib/api/types";
import { arr, asRec, str, Card, JsonBlock, Pill, SectionTitle } from "./ui";

/** Story copilot: outline (fast) or full draft (with scene prose). */
export function CopilotPanel() {
  const [premise, setPremise] = useState("");
  const [workingTitle, setWorkingTitle] = useState("");
  const [genre, setGenre] = useState("thriller");
  const [language, setLanguage] = useState("en");
  const [chapters, setChapters] = useState("8");
  const [tone, setTone] = useState("");

  const outline = useCopilotOutline();
  const draft = useCopilotDraft();
  const active = draft.isPending || draft.data ? draft : outline;

  const req = (): StoryOutlineRequest => ({
    premise,
    working_title: workingTitle,
    genre,
    language,
    target_chapters: Number(chapters) || 8,
    tone,
  });

  const result = asRec(active.data);
  const chapterBeats = arr(result.chapters).map(asRec);
  const characters = arr(result.characters).map(asRec);

  return (
    <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
      <Card className="space-y-4">
        <SectionTitle title="Story copilot" subtitle="Screened & demand-anchored (GOAT)." />
        <div>
          <label className="px-1 text-sm font-medium text-foreground">Premise</label>
          <textarea
            value={premise}
            onChange={(e) => setPremise(e.target.value)}
            rows={4}
            placeholder="A one-paragraph premise (min 10 chars)…"
            className="mt-1.5 w-full rounded-2xl border border-border bg-transparent px-4 py-3 text-sm text-foreground outline-none placeholder:text-muted-foreground/60 focus:border-foreground/40"
          />
        </div>
        <Input label="Working title" value={workingTitle} onChange={setWorkingTitle} />
        <div className="grid grid-cols-2 gap-3">
          <Input label="Genre" value={genre} onChange={setGenre} />
          <Input label="Language" value={language} onChange={setLanguage} />
          <Input label="Chapters" value={chapters} onChange={setChapters} inputMode="numeric" />
          <Input label="Tone" value={tone} onChange={setTone} placeholder="tense, wry…" />
        </div>
        <div className="flex gap-3">
          <Button
            type="button"
            onClick={() => outline.mutate(req())}
            disabled={outline.isPending || premise.length < 10}
          >
            {outline.isPending ? "Outlining…" : "Generate outline"}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => draft.mutate({ ...req(), scenes_to_write: 2 })}
            disabled={draft.isPending || premise.length < 10}
          >
            {draft.isPending ? "Writing…" : "Write draft"}
          </Button>
        </div>
      </Card>

      <div className="space-y-4">
        {active.isPending ? (
          <Card className="flex items-center gap-3">
            <Loader variant="scramble" size={28} />
            <span className="text-sm text-muted-foreground">Generating…</span>
          </Card>
        ) : active.isError ? (
          <Card className="text-sm text-destructive">
            {active.error instanceof Error ? active.error.message : "Generation failed."}
          </Card>
        ) : active.data ? (
          <>
            <Card>
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-lg font-bold text-foreground">
                  {str(result.working_title, "Untitled")}
                </h3>
                <Pill>{str(result.generated_by, "generated")}</Pill>
              </div>
              {str(result.logline) ? (
                <p className="mt-1 text-sm italic text-muted-foreground">{str(result.logline)}</p>
              ) : null}
              {str(result.setting) ? (
                <p className="mt-2 text-sm text-foreground/90">{str(result.setting)}</p>
              ) : null}
              {characters.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {characters.map((c, i) => (
                    <Pill key={i}>{str(c.name ?? c.role)}</Pill>
                  ))}
                </div>
              ) : null}
            </Card>

            {chapterBeats.length ? (
              <Card>
                <p className="mb-3 text-xs uppercase tracking-wide text-muted-foreground">
                  Chapter beats
                </p>
                <ol className="space-y-3">
                  {chapterBeats.map((c, i) => (
                    <li key={i} className="border-l-2 border-primary/40 pl-3">
                      <p className="font-medium text-foreground">
                        {num0(c.index, i + 1)}. {str(c.title)}
                      </p>
                      <p className="text-sm text-muted-foreground">{str(c.beat)}</p>
                      {str(c.hook) ? (
                        <p className="mt-0.5 text-xs text-primary/80">Hook: {str(c.hook)}</p>
                      ) : null}
                    </li>
                  ))}
                </ol>
              </Card>
            ) : null}

            <JsonBlock data={active.data} label="Full copilot response (incl. scenes / goat_trace)" />
          </>
        ) : (
          <Card className="text-sm text-muted-foreground">
            Enter a premise and generate an outline. The premise is screened against the catalog
            first — if it would be blocked at upload, nothing is written.
          </Card>
        )}
      </div>
    </div>
  );
}

function num0(v: unknown, fallback: number): number {
  return typeof v === "number" ? v : fallback;
}
