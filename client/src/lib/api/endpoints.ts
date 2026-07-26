// One function per server route — the complete surface of the PocketTaste API.
// Pure transport, no React. Hooks in src/hooks/api/ wrap these with React Query.

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
  EvaluationRequest,
  JsonRecord,
  LoginRequest,
  MyRecommendationRequest,
  NarrateRequest,
  PipelineRunRequest,
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
  scheme: () => http.get<JsonRecord>("/auth/scheme").then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Catalog
// ---------------------------------------------------------------------------

export const catalogApi = {
  list: (params: CatalogQuery = {}) =>
    http.get<ContentResponse[]>("/catalog", { params }).then((r) => r.data),
  get: (contentId: string) =>
    http.get<ContentDetailResponse>(`/catalog/${contentId}`).then((r) => r.data),
  transcript: (contentId: string) =>
    http
      .get<{ content_id: string; title: string; transcript: string }>(
        `/catalog/${contentId}/transcript`,
      )
      .then((r) => r.data),
  audio: (contentId: string) =>
    http
      .get<{
        content_id: string;
        title: string;
        has_audio: boolean;
        format: string | null;
        language: string;
        source: string;
        audio_base64: string;
      }>(`/catalog/${contentId}/audio`)
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
    http.post<ActivityAcceptedResponse>("/activity", body).then((r) => r.data),
  logBatch: (events: ActivityCreate[]) =>
    http
      .post<ActivityAcceptedResponse>("/activity/batch", { events })
      .then((r) => r.data),
  schema: () => http.get<JsonRecord>("/activity/schema").then((r) => r.data),
  stats: () => http.get<JsonRecord>("/activity/stats").then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Recommendations
// ---------------------------------------------------------------------------

export const recommendationsApi = {
  forUser: (body: RecommendationRequest) =>
    http.post<RecommendationResult>("/recommendations", body).then((r) => r.data),
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
  pipeline: () => http.get<JsonRecord>("/discovery/pipeline").then((r) => r.data),
  reindex: () => http.post<JsonRecord>("/discovery/reindex").then((r) => r.data),
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
// Analytics
// ---------------------------------------------------------------------------

export const analyticsApi = {
  content: (contentId: string) =>
    http.get<JsonRecord>(`/analytics/content/${contentId}`).then((r) => r.data),
  contentDropOff: (contentId: string) =>
    http
      .get<JsonRecord>(`/analytics/content/${contentId}/drop-off`)
      .then((r) => r.data),
  user: (userId: string) =>
    http.get<JsonRecord>(`/analytics/user/${userId}`).then((r) => r.data),
  creator: (creatorId: string) =>
    http.get<JsonRecord>(`/analytics/creators/${creatorId}`).then((r) => r.data),
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
  audit: (limit = 25) =>
    http
      .get<JsonRecord>("/similarity/audit", { params: { limit } })
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
      .get<JsonRecord>("/creator/opportunities", { params: { limit, language } })
      .then((r) => r.data),
  performance: () =>
    http.get<JsonRecord>("/creator/performance").then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Copilot
// ---------------------------------------------------------------------------

// GOAT's staged chain and the Sarvam finishing stage are each several sequential
// LLM/TTS calls — comfortably past the client's default 30s timeout even though
// the server itself isn't stuck. Override per-request rather than raising the
// global timeout, since every other endpoint really should fail fast at 30s.
const SLOW_GENERATION_TIMEOUT_MS = 240_000;

export const copilotApi = {
  outline: (body: StoryOutlineRequest) =>
    http
      .post<JsonRecord>("/copilot/outline", body, { timeout: SLOW_GENERATION_TIMEOUT_MS })
      .then((r) => r.data),
  draft: (body: StoryDraftRequest) =>
    http
      .post<JsonRecord>("/copilot/draft", body, { timeout: SLOW_GENERATION_TIMEOUT_MS })
      .then((r) => r.data),
  narrate: (body: NarrateRequest) =>
    http
      .post<JsonRecord>("/copilot/narrate", body, { timeout: SLOW_GENERATION_TIMEOUT_MS })
      .then((r) => r.data),
  engine: () => http.get<JsonRecord>("/copilot/engine").then((r) => r.data),
  guardrails: () => http.get<JsonRecord>("/copilot/guardrails").then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Pipeline / ops
// ---------------------------------------------------------------------------

export const pipelineApi = {
  run: (body: PipelineRunRequest = {}) =>
    http.post<JsonRecord>("/pipeline/run", body).then((r) => r.data),
  runs: (limit = 10) =>
    http
      .get<JsonRecord>("/pipeline/runs", { params: { limit } })
      .then((r) => r.data),
  runDetail: (runId: string) =>
    http.get<JsonRecord>(`/pipeline/runs/${runId}`).then((r) => r.data),
  describe: () => http.get<JsonRecord>("/pipeline/describe").then((r) => r.data),
  scheduler: () => http.get<JsonRecord>("/pipeline/scheduler").then((r) => r.data),
  schedulerTick: (force = false) =>
    http
      .post<JsonRecord>("/pipeline/scheduler/tick", null, { params: { force } })
      .then((r) => r.data),
  schedulerStart: () =>
    http.post<JsonRecord>("/pipeline/scheduler/start").then((r) => r.data),
  schedulerStop: () =>
    http.post<JsonRecord>("/pipeline/scheduler/stop").then((r) => r.data),
  databricks: () => http.get<JsonRecord>("/pipeline/databricks").then((r) => r.data),
  cacheInvalidate: () =>
    http.post<JsonRecord>("/pipeline/cache/invalidate").then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Evaluation
// ---------------------------------------------------------------------------

export const evaluationApi = {
  run: (body: EvaluationRequest = {}) =>
    http.post<JsonRecord>("/evaluation/run", body).then((r) => r.data),
  method: () => http.get<JsonRecord>("/evaluation/method").then((r) => r.data),
};

// ---------------------------------------------------------------------------
// System
// ---------------------------------------------------------------------------

export const systemApi = {
  index: () => http.get<JsonRecord>("/").then((r) => r.data),
  health: () => http.get<JsonRecord>("/health").then((r) => r.data),
  architecture: () =>
    http.get<JsonRecord>("/system/architecture").then((r) => r.data),
};
