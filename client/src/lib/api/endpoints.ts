// One function per server route. Pure transport — no React, no caching.
// Hooks in src/hooks/api/ wrap these with React Query.

import { http } from "./client";
import type {
  AccountResponse,
  ActivityAcceptedResponse,
  ActivityCreate,
  CatalogQuery,
  ContentCreate,
  ContentDetailResponse,
  ContentIngestResponse,
  ContentResponse,
  DiscoveryRequest,
  DiscoveryResponse,
  JsonRecord,
  LoginRequest,
  MyRecommendationRequest,
  RecommendationRequest,
  RecommendationResult,
  RegisterRequest,
  SimilarityCheckRequest,
  StoryDraftRequest,
  StoryOutlineRequest,
  TokenResponse,
} from "./types";

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export const authApi = {
  register: (body: RegisterRequest) =>
    http.post<TokenResponse>("/auth/register", body).then((r) => r.data),
  login: (body: LoginRequest) =>
    http.post<TokenResponse>("/auth/login", body).then((r) => r.data),
  me: () => http.get<AccountResponse>("/auth/me").then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Catalog
// ---------------------------------------------------------------------------

export const catalogApi = {
  list: (params: CatalogQuery = {}) =>
    http
      .get<ContentResponse[]>("/catalog", { params })
      .then((r) => r.data),
  get: (contentId: string) =>
    http
      .get<ContentDetailResponse>(`/catalog/${contentId}`)
      .then((r) => r.data),
  transcript: (contentId: string) =>
    http
      .get<{ content_id: string; title: string; transcript: string }>(
        `/catalog/${contentId}/transcript`,
      )
      .then((r) => r.data),
  create: (body: ContentCreate, screen = true) =>
    http
      .post<ContentIngestResponse>("/catalog", body, { params: { screen } })
      .then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Activity
// ---------------------------------------------------------------------------

export const activityApi = {
  log: (body: ActivityCreate) =>
    http
      .post<ActivityAcceptedResponse>("/activity", body)
      .then((r) => r.data),
  logBatch: (events: ActivityCreate[]) =>
    http
      .post<ActivityAcceptedResponse>("/activity/batch", { events })
      .then((r) => r.data),
  stats: () => http.get<JsonRecord>("/activity/stats").then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Recommendations
// ---------------------------------------------------------------------------

export const recommendationsApi = {
  forUser: (body: RecommendationRequest) =>
    http
      .post<RecommendationResult>("/recommendations", body)
      .then((r) => r.data),
  forMe: (body: MyRecommendationRequest) =>
    http
      .post<RecommendationResult>("/me/recommendations", body)
      .then((r) => r.data),
  weights: () =>
    http.get<JsonRecord>("/recommendations/weights").then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Discovery / search
// ---------------------------------------------------------------------------

export const discoveryApi = {
  search: (body: DiscoveryRequest) =>
    http.post<DiscoveryResponse>("/discovery/search", body).then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Me (signed-in listener)
// ---------------------------------------------------------------------------

export const meApi = {
  profile: () => http.get<JsonRecord>("/me/profile").then((r) => r.data),
  history: (limit = 100) =>
    http.get<JsonRecord>("/me/history", { params: { limit } }).then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Similarity
// ---------------------------------------------------------------------------

export const similarityApi = {
  check: (body: SimilarityCheckRequest) =>
    http.post<JsonRecord>("/similarity/check", body).then((r) => r.data),
  duplicates: (minRisk = 0.6) =>
    http
      .get<JsonRecord>("/similarity/duplicates", { params: { min_risk: minRisk } })
      .then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Insights / creator
// ---------------------------------------------------------------------------

export const insightsApi = {
  demand: (refresh = false) =>
    http
      .get<JsonRecord>("/insights/demand", { params: { refresh } })
      .then((r) => r.data),
  opportunities: (limit = 10) =>
    http
      .get<JsonRecord>("/insights/opportunities", { params: { limit } })
      .then((r) => r.data),
  saturation: () => http.get<JsonRecord>("/insights/saturation").then((r) => r.data),
  briefs: () => http.get<JsonRecord>("/insights/briefs").then((r) => r.data),
};

export const creatorApi = {
  opportunities: (limit = 5, language?: string) =>
    http
      .get<JsonRecord>("/creator/opportunities", {
        params: { limit, language },
      })
      .then((r) => r.data),
  performance: () =>
    http.get<JsonRecord>("/creator/performance").then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Copilot
// ---------------------------------------------------------------------------

export const copilotApi = {
  outline: (body: StoryOutlineRequest) =>
    http.post<JsonRecord>("/copilot/outline", body).then((r) => r.data),
  draft: (body: StoryDraftRequest) =>
    http.post<JsonRecord>("/copilot/draft", body).then((r) => r.data),
};

// ---------------------------------------------------------------------------
// System
// ---------------------------------------------------------------------------

export const systemApi = {
  health: () => http.get<JsonRecord>("/health").then((r) => r.data),
  index: () => http.get<JsonRecord>("/").then((r) => r.data),
};
