"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { Input } from "@/components/motion/input";
import { Button, StatefulButton, type ButtonState } from "@/components/motion/button";
import { Loader } from "@/components/motion/loader";
import { useUploadContent } from "@/hooks/api/use-catalog";
import { useCopilotDraft, useCopilotNarrate, useCopilotOutline } from "@/hooks/api/use-creator";
import { ApiError } from "@/lib/api/client";
import type { ContentCreate, StoryOutlineRequest } from "@/lib/api/types";
import type { CopilotSeed } from "./studio-shell";
import { arr, asRec, str, type Rec, Card, JsonBlock, Pill, SectionTitle } from "./ui";

/** ISO code -> label, for the "convert to voice" target-language picker. Matches
 * the backend's Sarvam-supported locale table (see sarvam_finishing.py). */
const INDIC_LANGUAGES: { value: string; label: string }[] = [
  { value: "", label: "Same language (no translation)" },
  { value: "hi", label: "Hindi" },
  { value: "ta", label: "Tamil" },
  { value: "te", label: "Telugu" },
  { value: "bn", label: "Bengali" },
  { value: "mr", label: "Marathi" },
  { value: "kn", label: "Kannada" },
  { value: "gu", label: "Gujarati" },
  { value: "ml", label: "Malayalam" },
  { value: "pa", label: "Punjabi" },
  { value: "od", label: "Odia" },
];

/** Languages Sarvam can actually narrate directly. A demand segment can be
 * labelled something Sarvam has no locale for (e.g. "hinglish") — the auto
 * pipeline falls back to narrating in Hindi rather than failing outright. */
const SARVAM_TTS_LANGUAGES = new Set(["en", ...INDIC_LANGUAGES.map((l) => l.value).filter(Boolean)]);

/** Races a promise against a hard deadline so a slow GOAT/Sarvam call surfaces
 * as a clear timeout error instead of leaving the automation banner spinning
 * with no way to tell "still working" from "stuck". */
function withTimeout<T>(promise: Promise<T>, ms: number, label: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error(`${label} took longer than ${Math.round(ms / 1000)}s — stopped.`)),
      ms,
    );
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (err) => {
        clearTimeout(timer);
        reject(err);
      },
    );
  });
}

/** Text to narrate: full scene prose if it exists (from `/copilot/draft`), else
 * the chapter beats (from the much cheaper `/copilot/outline` — no scene-writing
 * calls at all). Letting either shape flow through the same path is what lets
 * the automated pipeline use the fast outline while the manual "Write draft"
 * button still gets full prose. */
function extractNarrationText(data: unknown): string {
  const rec = asRec(data);
  const scenes = arr(rec.scenes);
  if (scenes.length) {
    return scenes.map((s) => str(asRec(s).text)).join("\n\n");
  }
  return arr(rec.chapters)
    .map((c) => {
      const chapter = asRec(c);
      return [str(chapter.title), str(chapter.beat), str(chapter.hook)]
        .filter(Boolean)
        .join(". ");
    })
    .join("\n\n");
}

/** Builds the POST /catalog body from a draft + finishing-stage response pair.
 * Shared by the manual "Publish" button and the automatic Opportunities flow,
 * so both take the exact same path from generated text to a stored story. */
function buildPublishBody(
  draftData: Rec,
  narrateData: Rec,
  ctx: { genre: string; premise: string; workingTitle: string; fallbackLanguage: string },
): ContentCreate {
  const narrationText = extractNarrationText(draftData);
  const narrateResult = asRec(narrateData);
  const narrateStage = asRec(narrateResult.narrate);
  const localizeStage = asRec(narrateResult.localize);
  const finalLanguage = str(narrateResult.final_language, ctx.fallbackLanguage);
  const finalText = localizeStage.ran ? str(localizeStage.text) : narrationText;
  const title = (str(draftData.working_title) || ctx.workingTitle || ctx.premise).slice(0, 200).trim();

  return {
    title: title.length >= 2 ? title : `${title || "Untitled"} story`,
    description: (str(draftData.logline) || ctx.premise).slice(0, 4000),
    transcript: finalText,
    language: finalLanguage,
    genres: [ctx.genre || "general"],
    duration_seconds: Math.max(60, Math.round((finalText.split(/\s+/).length / 150) * 60)),
    audio_base64: str(narrateStage.audio_base64),
    audio_language: finalLanguage,
    audio_source: "sarvam_tts",
  };
}

type AutoStage = "idle" | "drafting" | "narrating" | "publishing" | "done" | "error";

const AUTO_STAGE_LABEL: Record<AutoStage, string> = {
  idle: "",
  drafting: "Generating the outline with GOAT…",
  narrating: "Running the Sarvam finishing stage (polish, localize, narrate)…",
  publishing: "Publishing the finished story…",
  done: "Published — redirecting to the home page…",
  error: "Automation stopped",
};

/** Story copilot: outline (fast) or full draft (with scene prose), then an
 * optional Sarvam finishing stage — voice narration and publishing. Picking an
 * opportunity from the Opportunities tab runs the whole chain automatically. */
export function CopilotPanel({ seed }: { seed: CopilotSeed | null }) {
  const router = useRouter();
  const [premise, setPremise] = useState("");
  const [workingTitle, setWorkingTitle] = useState("");
  const [genre, setGenre] = useState("thriller");
  const [language, setLanguage] = useState("en");
  const [chapters, setChapters] = useState("8");
  const [tone, setTone] = useState("");
  const [targetLanguage, setTargetLanguage] = useState("");

  // Prefill from an Opportunities-tab pick. Adjusted during render (not an effect)
  // per React's "you might not need an effect" guidance: keyed on seedId so
  // re-picking the same segment still re-applies.
  const [appliedSeedId, setAppliedSeedId] = useState<number | null>(null);
  if (seed && seed.seedId !== appliedSeedId) {
    setAppliedSeedId(seed.seedId);
    setPremise(seed.premise);
    setGenre(seed.genre);
    setLanguage(seed.language);
    setWorkingTitle(seed.workingTitle);
  }

  const outline = useCopilotOutline();
  const draft = useCopilotDraft();
  const narrate = useCopilotNarrate();
  const upload = useUploadContent();
  // Tracks which action the user actually took, so a failed/timed-out draft shows
  // its own error instead of silently falling back to a stale outline result.
  const [mode, setMode] = useState<"outline" | "draft">("outline");
  const active = mode === "draft" ? draft : outline;
  // The language the draft was actually WRITTEN in, snapshotted at generation
  // time. The "Language" box above stays editable afterward (to start a new
  // draft), but narration/publish must never read the live, possibly
  // mid-edit/invalid value out of it — that both mislabels the source language
  // for TTS and can send a single-character value that fails backend validation.
  const [draftLanguage, setDraftLanguage] = useState("en");

  // --- automatic end-to-end pipeline, triggered by an Opportunities pick ----
  const [autoSeedId, setAutoSeedId] = useState<number | null>(null);
  const [autoStage, setAutoStage] = useState<AutoStage>("idle");
  const [autoError, setAutoError] = useState("");

  // Arms the pipeline during render (not in the effect below) per React's
  // "adjusting state during render" guidance — the effect's own body must stay
  // pure sync-setState-free so it isn't mistaken for one that just needs deriving.
  if (seed && seed.seedId !== autoSeedId) {
    setAutoSeedId(seed.seedId);
    setAutoStage("drafting");
    setAutoError("");
    // The auto pipeline uses the outline endpoint (see effect below) — no scene
    // prose, ~3x faster — and narrates the chapter beats instead.
    setMode("outline");
    setDraftLanguage(seed.language);
  }

  // Guards which seedId has actually started its async chain. Deliberately a
  // ref, not state: the effect below must NOT re-run every time its own
  // setAutoStage calls fire, or its cleanup would cancel the very chain it just
  // advanced (autoStage can't safely be a dependency of this effect).
  const startedSeedId = useRef<number | null>(null);

  useEffect(() => {
    if (!seed || startedSeedId.current === seed.seedId) return;
    const seedId = seed.seedId;
    startedSeedId.current = seedId;

    // Abandon-if-superseded is checked against the ref itself, NOT a per-run
    // closure flag: Next's dev server runs Strict Mode, which deliberately
    // mounts -> cleans up -> remounts every effect once. A closure-scoped
    // `cancelled` flag set by that spurious cleanup would kill the one real
    // chain right after its first await, every time, in dev. The ref persists
    // across that remount and only ever changes when a genuinely different
    // seed is picked, so checking against it is safe in both dev and prod.
    const stillCurrent = () => startedSeedId.current === seedId;

    (async () => {
      try {
        // Outline, not draft: GOAT's book-spec + plot-chapters stages only —
        // skips scene-splitting and scene-writing entirely (each a full
        // creative-generation LLM call), measured ~3x faster in practice. The
        // automated pipeline narrates the chapter beats instead of scene prose.
        const draftData = (await withTimeout(
          outline.mutateAsync({
            premise: seed.premise,
            working_title: seed.workingTitle,
            genre: seed.genre,
            language: seed.language,
            target_chapters: 8,
            tone: "",
          }),
          90_000,
          "Generating the outline",
        )) as Rec;
        if (!stillCurrent()) return;

        const narrationText = extractNarrationText(draftData);
        if (!narrationText) {
          setAutoStage("error");
          setAutoError(
            str(draftData.notice) ||
              "The outline came back with no chapters (often the similarity gate blocked it) — nothing to narrate.",
          );
          return;
        }

        setAutoStage("narrating");
        const supported = SARVAM_TTS_LANGUAGES.has(seed.language);
        const narrateData = (await withTimeout(
          narrate.mutateAsync({
            text: narrationText,
            language: supported ? seed.language : "en",
            localize_to: supported ? null : "hi",
          }),
          150_000,
          "The Sarvam finishing stage",
        )) as Rec;
        if (!stillCurrent()) return;

        setAutoStage("publishing");
        const body = buildPublishBody(draftData, narrateData, {
          genre: seed.genre,
          premise: seed.premise,
          workingTitle: seed.workingTitle,
          fallbackLanguage: seed.language,
        });
        await withTimeout(upload.mutateAsync({ body }), 30_000, "Publishing");
        if (!stillCurrent()) return;

        setAutoStage("done");
        setTimeout(() => {
          if (stillCurrent()) router.push("/");
        }, 1200);
      } catch (err) {
        if (!stillCurrent()) return;
        setAutoStage("error");
        setAutoError(err instanceof Error ? err.message : "Automation failed.");
      }
    })();
    // draft/narrate/upload are stable mutation objects from React Query, and
    // startedSeedId (a ref) intentionally isn't a dependency — only a new `seed`
    // identity should ever (re-)run this.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed]);

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
  const narrationText = extractNarrationText(active.data);
  // Either mode can be narrated now: outline gives chapter beats (fast), draft
  // gives full scene prose (slower, more expensive, more polished audio).
  const canNarrate = active.isSuccess && narrationText.length > 0;
  const isAutomating = autoStage !== "idle" && autoStage !== "error" && autoStage !== "done";

  const narrateResult = asRec(narrate.data);
  const narrateStage = asRec(narrateResult.narrate);
  const localizeStage = asRec(narrateResult.localize);
  const audioBase64 = str(narrateStage.audio_base64);

  function publish() {
    upload.mutate({
      body: buildPublishBody(result, narrateResult, {
        genre,
        premise,
        workingTitle,
        fallbackLanguage: draftLanguage,
      }),
    });
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
      <Card className="space-y-4">
        <SectionTitle title="Story copilot" subtitle="Screened & demand-anchored (GOAT)." />

        {autoStage !== "idle" ? (
          <div
            className={`rounded-2xl border px-4 py-3 text-sm ${
              autoStage === "error"
                ? "border-destructive/30 bg-destructive/10 text-destructive"
                : "border-primary/30 bg-primary/10 text-foreground"
            }`}
          >
            <div className="flex items-center gap-2 font-medium">
              {isAutomating ? <Loader variant="dots" size={16} /> : null}
              {AUTO_STAGE_LABEL[autoStage]}
            </div>
            {autoStage === "error" && autoError ? (
              <p className="mt-1 text-xs opacity-90">{autoError}</p>
            ) : null}
          </div>
        ) : null}

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
            onClick={() => {
              setMode("outline");
              setDraftLanguage(language);
              outline.mutate(req());
            }}
            disabled={outline.isPending || premise.length < 10}
          >
            {outline.isPending ? "Outlining…" : "Generate outline"}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setMode("draft");
              setDraftLanguage(language);
              draft.mutate({ ...req(), scenes_to_write: 2 });
            }}
            disabled={draft.isPending || premise.length < 10}
          >
            {draft.isPending ? "Writing…" : "Write draft"}
          </Button>
        </div>

        {canNarrate ? (
          <div className="space-y-3 border-t border-white/10 pt-4">
            <p className="text-sm font-medium text-foreground">Convert to voice</p>
            <p className="text-xs text-muted-foreground">
              Draft was written in <span className="text-foreground">{draftLanguage}</span>.
              Pick a different language below to translate it before narrating — editing the
              &ldquo;Language&rdquo; box above only affects a new draft, not this one.
            </p>
            <label className="block">
              <span className="px-1 text-xs text-muted-foreground">Narrate in</span>
              <select
                value={targetLanguage}
                onChange={(e) => setTargetLanguage(e.target.value)}
                className="mt-1 w-full rounded-2xl border border-border bg-transparent px-4 py-2.5 text-sm text-foreground outline-none focus:border-foreground/40"
              >
                {INDIC_LANGUAGES.map((l) => (
                  <option key={l.value} value={l.value} className="bg-background">
                    {l.label}
                  </option>
                ))}
              </select>
            </label>
            <Button
              type="button"
              onClick={() =>
                narrate.mutate({
                  text: narrationText,
                  language: draftLanguage,
                  localize_to: targetLanguage || null,
                })
              }
              disabled={narrate.isPending}
            >
              {narrate.isPending ? "Narrating…" : "Convert to voice"}
            </Button>
            {narrate.isError ? (
              <p className="text-sm text-destructive">
                {narrate.error instanceof Error ? narrate.error.message : "Narration failed."}
              </p>
            ) : null}
          </div>
        ) : null}

        {audioBase64 ? (
          <div className="space-y-3 border-t border-white/10 pt-4">
            <p className="text-sm font-medium text-foreground">Preview</p>
            <audio controls className="w-full" src={`data:audio/wav;base64,${audioBase64}`} />
            <PublishButton onClick={publish} upload={upload} />
            {upload.isSuccess ? (
              <p className="text-sm text-emerald-400">
                Published as {str(asRec(upload.data).content_id)} — see it under “Newly
                Released” on the home page.
              </p>
            ) : null}
            {upload.isError ? (
              <p className="text-sm text-destructive">
                {upload.error instanceof ApiError ? upload.error.message : "Publish failed."}
              </p>
            ) : null}
          </div>
        ) : null}
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

            {narrate.data ? (
              <Card>
                <p className="mb-3 text-xs uppercase tracking-wide text-muted-foreground">
                  Sarvam finishing stage
                </p>
                <div className="flex flex-wrap gap-2 text-xs">
                  <Pill tone={asRec(narrateResult.polish).ran ? "good" : "neutral"}>
                    polish: {asRec(narrateResult.polish).ran ? "applied" : "skipped"}
                  </Pill>
                  <Pill tone={localizeStage.ran ? "good" : "neutral"}>
                    localize: {localizeStage.ran ? str(localizeStage.language) : "skipped"}
                  </Pill>
                  <Pill tone={narrateStage.ran ? "good" : "bad"}>
                    narrate: {narrateStage.ran ? "audio ready" : str(narrateStage.reason, "failed")}
                  </Pill>
                </div>
                <JsonBlock data={narrate.data} label="Full finishing response" />
              </Card>
            ) : null}

            <JsonBlock data={active.data} label="Full copilot response (incl. scenes / goat_trace)" />
          </>
        ) : (
          <Card className="text-sm text-muted-foreground">
            Enter a premise and generate an outline, or pick an opportunity from the
            Opportunities tab to run the whole chain automatically. The premise is screened
            against the catalog first — if it would be blocked at upload, nothing is written.
          </Card>
        )}
      </div>
    </div>
  );
}

function PublishButton({
  onClick,
  upload,
}: {
  onClick: () => void;
  upload: ReturnType<typeof useUploadContent>;
}) {
  const state: ButtonState = upload.isPending
    ? "loading"
    : upload.isError
      ? "error"
      : upload.isSuccess
        ? "success"
        : "idle";
  return (
    <StatefulButton
      type="button"
      state={state}
      onClick={onClick}
      loadingText="Publishing"
      successText="Published"
      errorText="Failed"
    >
      Publish as new story
    </StatefulButton>
  );
}

function num0(v: unknown, fallback: number): number {
  return typeof v === "number" ? v : fallback;
}
