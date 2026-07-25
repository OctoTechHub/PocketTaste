// React Query key factory. One flat place so queries and invalidations never
// drift out of sync over hand-written string arrays.

import type { CatalogQuery } from "./types";

export const queryKeys = {
  me: ["me"] as const,
  profile: ["me", "profile"] as const,
  history: (limit: number) => ["me", "history", limit] as const,

  catalog: (params: CatalogQuery) => ["catalog", params] as const,
  content: (id: string) => ["catalog", "detail", id] as const,

  activityStats: ["activity", "stats"] as const,
  recommendationWeights: ["recommendations", "weights"] as const,

  insightsDemand: ["insights", "demand"] as const,
  insightsOpportunities: (limit: number) =>
    ["insights", "opportunities", limit] as const,
  insightsSaturation: ["insights", "saturation"] as const,
  insightsBriefs: ["insights", "briefs"] as const,

  creatorOpportunities: (language?: string) =>
    ["creator", "opportunities", language ?? "all"] as const,
  creatorPerformance: ["creator", "performance"] as const,

  health: ["system", "health"] as const,
};
