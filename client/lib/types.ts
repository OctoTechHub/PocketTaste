// Client-side mirror of the server's public payloads (see server/app/api/serializers.py).

export interface Series {
  id: string;
  title: string;
  synopsis: string;
  genres: string[];
  language: string;
  tone: string[];
  pacing: string;
  episodeCount: number;
  avgEpisodeMinutes: number;
  narrator: string;
  isOriginal: boolean;
  isNew: boolean;
  popularity: number;
  coinPriceApprox: number;
  tags: string[];
}

export interface ScoreBreakdown {
  contentSimilarity: number;
  genreAffinity: number;
  languageMatch: number;
  toneMatch: number;
  pacingMatch: number;
  lengthFit: number;
  monetizationProxy: number;
  freshness: number;
  total: number;
}

export type CandidateSource = "content" | "collaborative" | "popularity" | "query";

export interface RankedSeries {
  series: Series;
  score: number;
  sources: CandidateSource[];
  reason: string | null;
  breakdown: ScoreBreakdown;
}

export interface FeedRail {
  key: string;
  title: string;
  subtitle: string | null;
  items: RankedSeries[];
}

export interface DiscoveryIntent {
  genres: string[];
  excludeGenres: string[];
  language: string | null;
  tones: string[];
  pacing: string | null;
  maxEpisodeMinutes: number | null;
  keywords: string[];
  moodText: string;
}

export interface UserSummary {
  id: string;
  displayName: string;
  languages: string[];
}

export interface TasteProfile {
  userId: string;
  eventCount: number;
  coinSpend: number;
  topGenre: string | null;
  topTone: string | null;
  topLanguage: string | null;
  avgPreferredEpisodeMinutes: number;
  genreAffinity: Record<string, number>;
  toneAffinity: Record<string, number>;
  languageAffinity: Record<string, number>;
  completedSeriesIds: string[];
  droppedSeriesIds: string[];
  recentSeriesIds: string[];
}

export type EventType =
  | "play"
  | "complete_episode"
  | "complete_series"
  | "skip_intro"
  | "drop"
  | "coin_unlock"
  | "rate";

export interface HealthInfo {
  status: string;
  mode: "openai" | "local-fallback";
  catalogSize: number;
}
