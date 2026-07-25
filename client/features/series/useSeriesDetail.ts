"use client";

import { api } from "@/lib/apiClient";
import { useAsync } from "@/lib/useAsync";
import type { RankedSeries, Series } from "@/lib/types";

interface SeriesDetail {
  series: Series;
  similar: RankedSeries[];
}

/** Loads a single series plus its "more like this" list. */
export function useSeriesDetail(seriesId: string | null) {
  return useAsync<SeriesDetail>(
    () => api.seriesDetail(seriesId as string),
    [seriesId],
    Boolean(seriesId),
  );
}
