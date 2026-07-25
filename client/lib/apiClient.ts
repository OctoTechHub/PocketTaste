// Single typed boundary to the PocketTaste API. No component talks to fetch directly.
import type {
  DiscoveryIntent,
  EventType,
  FeedRail,
  HealthInfo,
  RankedSeries,
  Series,
  TasteProfile,
  UserSummary,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:4000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`API ${res.status} ${path}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export interface EventPayload {
  userId: string;
  seriesId: string;
  type: EventType;
  episodeIndex?: number;
  completionPct?: number;
  coins?: number;
  value?: number;
}

export const api = {
  health: () => request<HealthInfo>("/api/health"),

  users: () => request<{ users: UserSummary[] }>("/api/users").then((r) => r.users),

  feed: (userId: string) =>
    request<{ rails: FeedRail[] }>(`/api/feed?user_id=${encodeURIComponent(userId)}`).then(
      (r) => r.rails,
    ),

  profile: (userId: string) =>
    request<{ profile: TasteProfile }>(
      `/api/profile?user_id=${encodeURIComponent(userId)}`,
    ).then((r) => r.profile),

  discover: (query: string, userId?: string) =>
    request<{ intent: DiscoveryIntent; results: RankedSeries[] }>("/api/discover", {
      method: "POST",
      body: JSON.stringify({ query, user_id: userId }),
    }),

  seriesDetail: (id: string) =>
    request<{ series: Series; similar: RankedSeries[] }>(`/api/series/${encodeURIComponent(id)}`),

  logEvent: (payload: EventPayload) =>
    request<{ ok: boolean }>("/api/events", {
      method: "POST",
      body: JSON.stringify({
        user_id: payload.userId,
        series_id: payload.seriesId,
        type: payload.type,
        episode_index: payload.episodeIndex,
        completion_pct: payload.completionPct,
        coins: payload.coins,
        value: payload.value,
      }),
    }),
};
