"use client";

import { useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { Button, StatefulButton, type ButtonState } from "@/components/motion/button";
import { Input } from "@/components/motion/input";
import { Loader } from "@/components/motion/loader";
import {
  useInvalidateCache,
  usePipelineRuns,
  useRunEvaluation,
  useRunPipeline,
  useScheduler,
  useSchedulerControls,
} from "@/hooks/api/use-pipeline";
import { useDuplicates, useSimilarityAudit } from "@/hooks/api/use-creator";
import { useHealth, useReindex } from "@/hooks/api/use-system";
import {
  activityApi,
  authApi,
  copilotApi,
  discoveryApi,
  evaluationApi,
  pipelineApi,
  recommendationsApi,
  systemApi,
} from "@/lib/api/endpoints";
import {
  arr,
  asRec,
  num,
  str,
  Card,
  JsonBlock,
  Pill,
  SectionTitle,
  StatTile,
} from "@/components/studio/ui";
import { ReferenceCard } from "./reference-card";

/** Admin / Ops — pipeline, scheduler, evaluation, maintenance, and every introspection route. */
export function AdminShell() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main className="mx-auto max-w-6xl space-y-8 px-4 pb-20 pt-24 sm:px-8">
        <header>
          <p className="text-xs font-black uppercase tracking-[0.2em] text-primary">Admin · Ops</p>
          <h1 className="mt-1 text-2xl font-bold sm:text-3xl">Pipeline & platform controls</h1>
        </header>

        <ServiceSection />
        <PipelineSection />
        <EvaluationSection />
        <MaintenanceSection />
        <OriginalitySection />
        <ReferenceSection />
      </main>
    </div>
  );
}

// --- Service health ---------------------------------------------------------

function ServiceSection() {
  const { data, isLoading } = useHealth();
  const h = asRec(data);
  const catalog = asRec(h.catalog);
  return (
    <section>
      <SectionTitle title="Service" subtitle="GET /health (auto-refresh)" />
      {isLoading ? (
        <Card>Loading health…</Card>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatTile label="Status" value={str(h.status, "—")} />
          <StatTile label="Catalog items" value={num(catalog.content_items)} />
          <StatTile label="Activity events" value={num(catalog.activity_events)} />
          <StatTile label="Provenance" value={str(h.provenance, "—")} />
        </div>
      )}
    </section>
  );
}

// --- Pipeline ---------------------------------------------------------------

function PipelineSection() {
  const run = useRunPipeline();
  const runs = usePipelineRuns(8);
  const scheduler = useScheduler();
  const { tick, start, stop } = useSchedulerControls();

  const runState: ButtonState = run.isPending
    ? "loading"
    : run.isError
      ? "error"
      : run.isSuccess
        ? "success"
        : "idle";
  const sched = asRec(scheduler.data);
  const runList = arr(asRec(runs.data).runs).map(asRec);

  return (
    <section>
      <SectionTitle title="Pipeline" subtitle="Three-agent pipeline + background scheduler" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <StatefulButton
              state={runState}
              onClick={() => run.mutate({ use_llm: false })}
              loadingText="Running"
              successText="Done"
              errorText="Failed"
            >
              Run pipeline
            </StatefulButton>
            <span className="text-xs text-muted-foreground">POST /pipeline/run (llm off)</span>
          </div>

          <div className="rounded-xl border border-border p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">Scheduler</p>
              <Pill tone={sched.enabled ? "good" : "neutral"}>
                {sched.enabled ? "enabled" : "stopped"}
              </Pill>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              every {num(sched.interval_seconds ?? sched.background_pipeline_seconds)}s ·{" "}
              {num(sched.ticks ?? 0)} ticks
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={() => tick.mutate(true)} disabled={tick.isPending}>
                Tick now
              </Button>
              <Button size="sm" variant="outline" onClick={() => start.mutate()} disabled={start.isPending}>
                Start
              </Button>
              <Button size="sm" variant="outline" onClick={() => stop.mutate()} disabled={stop.isPending}>
                Stop
              </Button>
            </div>
          </div>
        </Card>

        <Card>
          <p className="mb-3 text-sm font-medium">Recent runs</p>
          {runs.isLoading ? (
            <Loader variant="dots" size={16} />
          ) : runList.length ? (
            <ul className="space-y-2 text-sm">
              {runList.map((r, i) => (
                <li key={i} className="flex items-center justify-between gap-2 border-b border-border/60 pb-2">
                  <span className="truncate font-mono text-xs text-muted-foreground">
                    {str(r.run_id, `run ${i + 1}`)}
                  </span>
                  <Pill tone={str(r.status) === "succeeded" ? "good" : str(r.status) === "failed" ? "bad" : "warn"}>
                    {str(r.status, "—")}
                  </Pill>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No runs yet.</p>
          )}
          {run.data ? <div className="mt-3"><JsonBlock data={run.data} label="Last run result" /></div> : null}
        </Card>
      </div>
    </section>
  );
}

// --- Evaluation -------------------------------------------------------------

function EvaluationSection() {
  const evaluate = useRunEvaluation();
  const [k, setK] = useState("10");

  return (
    <section>
      <SectionTitle title="Evaluation" subtitle="Recall@K / NDCG@K vs popularity & random baselines" />
      <Card className="space-y-3">
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-24">
            <Input label="k" value={k} onChange={setK} inputMode="numeric" />
          </div>
          <Button
            onClick={() => evaluate.mutate({ k: Number(k) || 10 })}
            disabled={evaluate.isPending}
          >
            {evaluate.isPending ? "Evaluating…" : "Run evaluation"}
          </Button>
          <span className="text-xs text-muted-foreground">POST /evaluation/run</span>
        </div>
        {evaluate.isError ? (
          <p className="text-sm text-destructive">
            {evaluate.error instanceof Error ? evaluate.error.message : "Failed."}
          </p>
        ) : null}
        {evaluate.data ? <JsonBlock data={evaluate.data} label="Evaluation report" /> : null}
      </Card>
    </section>
  );
}

// --- Maintenance ------------------------------------------------------------

function MaintenanceSection() {
  const cache = useInvalidateCache();
  const reindex = useReindex();
  return (
    <section>
      <SectionTitle title="Maintenance" subtitle="Serving cache & retrieval index" />
      <Card className="flex flex-wrap items-center gap-3">
        <Button variant="outline" onClick={() => cache.mutate()} disabled={cache.isPending}>
          {cache.isPending ? "Reloading…" : "Invalidate cache"}
        </Button>
        <Button variant="outline" onClick={() => reindex.mutate()} disabled={reindex.isPending}>
          {reindex.isPending ? "Reindexing…" : "Rebuild search index"}
        </Button>
        {cache.data ? <Pill tone="good">cache reloaded</Pill> : null}
        {reindex.data ? (
          <Pill tone="good">{num(asRec(reindex.data).indexed_documents)} indexed</Pill>
        ) : null}
      </Card>
    </section>
  );
}

// --- Originality ------------------------------------------------------------

function OriginalitySection() {
  const dupes = useDuplicates(0.6);
  const audit = useSimilarityAudit(15);
  const clusters = asRec(asRec(dupes.data).clusters);
  return (
    <section>
      <SectionTitle title="Originality" subtitle="Duplicate families & screening audit trail" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <p className="mb-2 text-sm font-medium">
            Flagged: {num(asRec(dupes.data).flagged_items)} across {Object.keys(clusters).length} clusters
          </p>
          {dupes.isLoading ? <Loader variant="dots" size={16} /> : <JsonBlock data={dupes.data} label="Duplicate families" />}
        </Card>
        <Card>
          <p className="mb-2 text-sm font-medium">
            Screening decisions: {num(asRec(audit.data).total_recorded)}
          </p>
          {audit.isLoading ? <Loader variant="dots" size={16} /> : <JsonBlock data={audit.data} label="Audit trail" />}
        </Card>
      </div>
    </section>
  );
}

// --- Reference (every describe / introspection route) -----------------------

function ReferenceSection() {
  const refs: { label: string; path: string; queryKey: readonly unknown[]; fetcher: () => Promise<unknown> }[] = [
    { label: "System architecture", path: "GET /system/architecture", queryKey: ["ref", "arch"], fetcher: systemApi.architecture },
    { label: "API index", path: "GET /", queryKey: ["ref", "index"], fetcher: systemApi.index },
    { label: "Ranker weights", path: "GET /recommendations/weights", queryKey: ["ref", "weights"], fetcher: recommendationsApi.weights },
    { label: "Event schema", path: "GET /activity/schema", queryKey: ["ref", "evt-schema"], fetcher: activityApi.schema },
    { label: "Activity stats", path: "GET /activity/stats", queryKey: ["ref", "evt-stats"], fetcher: activityApi.stats },
    { label: "Auth scheme", path: "GET /auth/scheme", queryKey: ["ref", "auth-scheme"], fetcher: authApi.scheme },
    { label: "Pipeline describe", path: "GET /pipeline/describe", queryKey: ["ref", "pipe-desc"], fetcher: pipelineApi.describe },
    { label: "Databricks spec", path: "GET /pipeline/databricks", queryKey: ["ref", "databricks"], fetcher: pipelineApi.databricks },
    { label: "Evaluation method", path: "GET /evaluation/method", queryKey: ["ref", "eval-method"], fetcher: evaluationApi.method },
    { label: "Retrieval pipeline", path: "GET /discovery/pipeline", queryKey: ["ref", "disc-pipe"], fetcher: discoveryApi.pipeline },
    { label: "Copilot engine", path: "GET /copilot/engine", queryKey: ["ref", "copilot-engine"], fetcher: copilotApi.engine },
    { label: "Copilot guardrails", path: "GET /copilot/guardrails", queryKey: ["ref", "copilot-guard"], fetcher: copilotApi.guardrails },
  ];

  return (
    <section>
      <SectionTitle title="Reference" subtitle="Self-documenting endpoints — fetch on demand" />
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {refs.map((r) => (
          <ReferenceCard key={r.path} {...r} />
        ))}
      </div>
    </section>
  );
}
