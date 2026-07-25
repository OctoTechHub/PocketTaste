// TypeScript mirrors of the FastAPI server's request/response DTOs.
// Source of truth: server/app/domain/schemas.py and enums.py. Keep in sync.

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export type EventType =
  | "play"
  | "pause"
  | "resume"
  | "skip"
  | "replay"
  | "complete"
  | "drop_off"
  | "chapter_jump"
  | "search"
  | "revisit";

export type Provenance =
  | "real"
  | "synthetic_simulation"
  | "simulated_from_real_catalog"
  | "mixed";

export type ContentSource = "platform" | "creator_upload" | "synthetic";

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface RegisterRequest {
  email: string;
  password: string;
  display_name?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AccountResponse {
  user_id: string;
  email: string;
  display_name: string;
  roles: string[];
  is_active: boolean;
  created_at: string;
  last_login_at?: string | null;
  login_count: number;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  expires_at: string;
  account: AccountResponse;
}

// ---------------------------------------------------------------------------
// Catalog
// ---------------------------------------------------------------------------

export interface ChapterInput {
  index: number;
  title: string;
  start_seconds: number;
  end_seconds: number;
  summary?: string;
}

export interface ContentCreate {
  content_id?: string | null;
  title: string;
  description: string;
  transcript: string;
  language?: string;
  genres?: string[];
  tags?: string[];
  duration_seconds?: number;
  chapters?: ChapterInput[];
  source?: ContentSource;
  published_at?: string | null;
}

export interface ContentResponse {
  content_id: string;
  title: string;
  description: string;
  creator_id: string;
  language: string;
  genres: string[];
  tags: string[];
  duration_seconds: number;
  chapter_count: number;
  source: ContentSource;
  is_synthetic: boolean;
  published_at: string;
  transcript_chars: number;
}

export interface ContentDetailResponse {
  content: ContentResponse;
  chapters: unknown[];
  profile?: Record<string, unknown> | null;
  features?: Record<string, unknown> | null;
}

export interface ContentIngestResponse {
  content_id: string;
  created: boolean;
  similarity_gate?: Record<string, unknown> | null;
  profile_queued: boolean;
}

export interface CatalogQuery {
  language?: string;
  genre?: string;
  creator_id?: string;
  limit?: number;
  offset?: number;
}

// ---------------------------------------------------------------------------
// Activity
// ---------------------------------------------------------------------------

export interface ActivityCreate {
  content_id?: string | null;
  session_id?: string | null;
  event_type: EventType;
  position_seconds?: number;
  chapter_index?: number | null;
  session_seconds?: number;
  query?: string | null;
  result_count?: number | null;
  device?: string;
  occurred_at?: string | null;
}

export interface ActivityAcceptedResponse {
  accepted: number;
  rejected: number;
  event_ids: string[];
  errors: string[];
}

// ---------------------------------------------------------------------------
// Recommendations
// ---------------------------------------------------------------------------

export interface MyRecommendationRequest {
  limit?: number;
  language?: string | null;
  exclude_content_ids?: string[];
  include_seen?: boolean;
  include_duplicates?: boolean;
  diversity?: number | null;
  explain?: boolean;
}

export interface RecommendationRequest extends MyRecommendationRequest {
  user_id: string;
}

export interface RecommendationItem {
  content_id: string;
  title: string;
  final_score: number;
  relevance_score: number;
  contributions?: Record<string, number>;
  language?: string;
  genres?: string[];
  reason?: string;
  [key: string]: unknown;
}

export interface RecommendationResult {
  items: RecommendationItem[];
  explanation?: string;
  explanation_source?: string;
  suppressed_duplicates?: number;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Discovery
// ---------------------------------------------------------------------------

export interface DiscoveryRequest {
  query: string;
  user_id?: string | null;
  language?: string | null;
  top_k?: number;
  answer?: boolean;
}

export interface DiscoveryHit {
  content_id: string;
  title: string;
  language: string;
  genres: string[];
  score: number;
  retrievers: string[];
  snippet: string;
}

export interface DiscoveryResponse {
  query: string;
  hits: DiscoveryHit[];
  answer?: string | null;
  pipeline: string;
  retrievers_used: string[];
  fusion: string;
  logged_as_search: boolean;
}

// ---------------------------------------------------------------------------
// Similarity
// ---------------------------------------------------------------------------

export interface SimilarityCheckRequest {
  title: string;
  description?: string;
  transcript?: string;
  language?: string;
  genres?: string[];
  chapters?: ChapterInput[];
  exclude_content_id?: string | null;
  top_k?: number;
  use_llm?: boolean;
}

// ---------------------------------------------------------------------------
// Copilot
// ---------------------------------------------------------------------------

export interface StoryOutlineRequest {
  premise: string;
  working_title?: string;
  genre?: string;
  language?: string;
  target_chapters?: number;
  tone?: string;
}

export interface StoryDraftRequest extends StoryOutlineRequest {
  scenes_to_write?: number;
}

// ---------------------------------------------------------------------------
// Generic record fallbacks for the analytics / insights / pipeline endpoints
// whose payloads are large, nested and mostly rendered as-is.
// ---------------------------------------------------------------------------

export type JsonRecord = Record<string, unknown>;
