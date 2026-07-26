// React Query key factory. One flat place so queries and invalidations never
// drift out of sync over hand-written string arrays.

import type { CatalogQuery } from "./types";

export const queryKeys = {
  me: ["me"] as const,
  profile: ["me", "profile"] as const,
  history: (limit: number) => ["me", "history", limit] as const,

  catalog: (params: CatalogQuery) => ["catalog", params] as const,
  content: (id: string) => ["catalog", "detail", id] as const,

  blends: ["blend"] as const,
  blend: (id: string) => ["blend", id] as const,
  blendFeed: (id: string, limit: number) => ["blend", id, "feed", limit] as const,

  activityStats: ["activity", "stats"] as const,
  activitySchema: ["activity", "schema"] as const,
  recommendationWeights: ["recommendations", "weights"] as const,

  insightsDemand: ["insights", "demand"] as const,
  insightsOpportunities: (limit: number) =>
    ["insights", "opportunities", limit] as const,
  insightsSaturation: ["insights", "saturation"] as const,
  insightsBriefs: ["insights", "briefs"] as const,

  creatorOpportunities: (language?: string) =>
    ["creator", "opportunities", language ?? "all"] as const,
  creatorPerformance: ["creator", "performance"] as const,

  analyticsContent: (id: string) => ["analytics", "content", id] as const,
  analyticsDropOff: (id: string) => ["analytics", "drop-off", id] as const,
  analyticsUser: (id: string) => ["analytics", "user", id] as const,
  analyticsCreator: (id: string) => ["analytics", "creator", id] as const,

  similarityDuplicates: (minRisk: number) =>
    ["similarity", "duplicates", minRisk] as const,
  similarityAudit: (limit: number) => ["similarity", "audit", limit] as const,

  pipelineRuns: (limit: number) => ["pipeline", "runs", limit] as const,
  pipelineRun: (id: string) => ["pipeline", "run", id] as const,
  pipelineDescribe: ["pipeline", "describe"] as const,
  pipelineScheduler: ["pipeline", "scheduler"] as const,
  pipelineDatabricks: ["pipeline", "databricks"] as const,

  evaluationMethod: ["evaluation", "method"] as const,

  copilotEngine: ["copilot", "engine"] as const,
  copilotGuardrails: ["copilot", "guardrails"] as const,

  discoveryPipeline: ["discovery", "pipeline"] as const,
  authScheme: ["auth", "scheme"] as const,

  health: ["system", "health"] as const,
  architecture: ["system", "architecture"] as const,
};
