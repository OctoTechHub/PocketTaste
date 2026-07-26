"use client";

import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { useMemo } from "react";

import { Loader } from "@/components/motion/loader";
import { SiteHeader } from "@/components/site-header";
import { WatchView } from "@/components/watch/watch-view";
import { useCatalog, useContent } from "@/hooks/api/use-catalog";
import { API_BASE_URL } from "@/lib/api/config";
import { contentToItem } from "@/lib/api/mappers";

/**
 * Resolves a watch page entirely from the API: GET /catalog/{id} for the item,
 * and same-genre catalog entries for the recommendations rail. No mock data.
 */
export function WatchScreen({ id }: { id: string }) {
  const { data, isLoading, isError } = useContent(id);

  const primaryGenre = data?.content.genres[0];
  // Related titles from the same genre; falls back to a broad slice.
  const related = useCatalog(
    primaryGenre ? { genre: primaryGenre, limit: 24 } : { limit: 24 },
  );

  const video = useMemo(() => {
    if (!data) return null;
    const item = contentToItem(data.content);
    // Stream the narration straight from the API (Range-capable) instead of
    // pulling a ~15MB base64 blob into memory and building a data: URI.
    if (data.content.has_audio) {
      item.audio = `${API_BASE_URL}/catalog/${id}/audio.wav`;
    }
    return item;
  }, [data, id]);
  const recommendations = useMemo(
    () => (related.data ?? []).filter((item) => item.id !== id).slice(0, 18),
    [related.data, id],
  );

  if (isLoading) {
    return (
      <Shell>
        <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-muted-foreground">
          <Loader variant="spinner" size={40} />
          <p className="text-sm">Loading story…</p>
        </div>
      </Shell>
    );
  }

  if (isError || !video) {
    return (
      <Shell>
        <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 px-6 text-center">
          <p className="text-lg font-semibold text-foreground">Story not found</p>
          <p className="max-w-md text-sm text-muted-foreground">
            This story isn’t in the catalog — it may have been unpublished, or the
            link may be out of date.
          </p>
          <Link
            href="/"
            className="mt-2 inline-flex items-center gap-1 text-sm text-primary hover:underline"
          >
            <ChevronLeft className="h-4 w-4" /> Back to browse
          </Link>
        </div>
      </Shell>
    );
  }

  return <WatchView video={video} recommendations={recommendations} />;
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main className="pt-20">{children}</main>
    </div>
  );
}
