"use client";

import { Sparkles } from "lucide-react";

import { ContentRow } from "@/components/content-row";
import { Loader } from "@/components/motion/loader";
import { useAuth } from "@/hooks/api/use-auth";
import { useMyRecommendations } from "@/hooks/api/use-recommendations";

/**
 * Personalised "For You" rail. Renders only for a signed-in listener; the data
 * is POST /me/recommendations, mapped to the same tiles as every other row.
 */
export function ForYouRow() {
  const { isAuthenticated } = useAuth();
  const { data, isLoading, isError } = useMyRecommendations({ limit: 12 });

  // Anonymous visitors don't get a personalised rail — nothing to show.
  if (!isAuthenticated) return null;

  if (isLoading) {
    return (
      <section className="py-3">
        <RowHeading />
        <div className="flex h-[170px] items-center gap-3 px-4 text-muted-foreground sm:px-12">
          <Loader variant="dots" size={22} />
          <span className="text-sm">Ranking stories for you…</span>
        </div>
      </section>
    );
  }

  if (isError || !data || data.items.length === 0) {
    return (
      <section className="py-3">
        <RowHeading />
        <p className="px-4 text-sm text-muted-foreground sm:px-12">
          No picks yet — play a few stories and they’ll show up here once the
          pipeline learns your taste.
        </p>
      </section>
    );
  }

  return (
    <ContentRow
      row={{ id: "for-you", label: "For You", titles: data.items }}
    />
  );
}

function RowHeading() {
  return (
    <h2 className="mb-2 flex items-center gap-2 px-4 text-lg font-bold text-foreground sm:px-12 md:text-xl">
      <Sparkles className="h-5 w-5 text-primary" />
      For You
    </h2>
  );
}
