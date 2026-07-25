"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { evaluationApi, pipelineApi } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import type { EvaluationRequest, PipelineRunRequest } from "@/lib/api/types";

// --- Pipeline queries -------------------------------------------------------

/** GET /pipeline/runs — recent pipeline runs. */
export function usePipelineRuns(limit = 10) {
  return useQuery({
    queryKey: queryKeys.pipelineRuns(limit),
    queryFn: () => pipelineApi.runs(limit),
  });
}

/** GET /pipeline/describe — agent roster and stage ordering. */
export function usePipelineDescribe() {
  return useQuery({
    queryKey: queryKeys.pipelineDescribe,
    queryFn: () => pipelineApi.describe(),
  });
}

/** GET /pipeline/scheduler — background loop status and cost. */
export function useScheduler() {
  return useQuery({
    queryKey: queryKeys.pipelineScheduler,
    queryFn: () => pipelineApi.scheduler(),
    refetchInterval: 15_000,
  });
}

/** GET /pipeline/databricks — batch-tier job specification. */
export function useDatabricksSpec() {
  return useQuery({
    queryKey: queryKeys.pipelineDatabricks,
    queryFn: () => pipelineApi.databricks(),
  });
}

// --- Pipeline mutations -----------------------------------------------------

/** POST /pipeline/run — run the three-agent pipeline. */
export function useRunPipeline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body?: PipelineRunRequest) => pipelineApi.run(body ?? {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pipeline"] });
      qc.invalidateQueries({ queryKey: ["insights"] });
      qc.invalidateQueries({ queryKey: ["catalog"] });
    },
  });
}

/** Scheduler controls: tick / start / stop. */
export function useSchedulerControls() {
  const qc = useQueryClient();
  const invalidate = () =>
    qc.invalidateQueries({ queryKey: queryKeys.pipelineScheduler });

  const tick = useMutation({
    mutationFn: (force?: boolean) => pipelineApi.schedulerTick(force ?? false),
    onSuccess: invalidate,
  });
  const start = useMutation({
    mutationFn: () => pipelineApi.schedulerStart(),
    onSuccess: invalidate,
  });
  const stop = useMutation({
    mutationFn: () => pipelineApi.schedulerStop(),
    onSuccess: invalidate,
  });
  return { tick, start, stop };
}

/** POST /pipeline/cache/invalidate — force the serving cache to reload. */
export function useInvalidateCache() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => pipelineApi.cacheInvalidate(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["catalog"] }),
  });
}

// --- Evaluation -------------------------------------------------------------

/** POST /evaluation/run — temporal-holdout evaluation against baselines. */
export function useRunEvaluation() {
  return useMutation({
    mutationFn: (body?: EvaluationRequest) => evaluationApi.run(body ?? {}),
  });
}

/** GET /evaluation/method — how the evaluation is set up. */
export function useEvaluationMethod() {
  return useQuery({
    queryKey: queryKeys.evaluationMethod,
    queryFn: () => evaluationApi.method(),
  });
}
