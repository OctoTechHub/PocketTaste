"use client";

import { ContentRow } from "@/components/content-row";
import { useNewReleases } from "@/hooks/api/use-catalog";

/**
 * Stories narrated end-to-end through the Studio copilot: GOAT draft, similarity
 * gate, Sarvam polish/localize/TTS, then published. Nothing to show until a
 * creator actually publishes one — no synthetic placeholder row.
 */
export function NewReleasesRow() {
  const { data, isLoading } = useNewReleases();

  if (isLoading || !data || data.length === 0) return null;

  return (
    <ContentRow
      row={{ id: "new-releases", label: "Newly Released", titles: data }}
    />
  );
}
