"use client";

import { Suspense, useMemo } from "react";
import { useSearchParams } from "next/navigation";

import { CopilotPanel } from "@/components/studio/copilot-panel";
import { getStudioTab } from "@/components/studio/tabs";
import { TabHeader } from "@/components/studio/ui";
import type { CopilotSeed } from "@/components/studio/studio-shell";

function hashNum(seed: string): number {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h);
}

function CopilotContent() {
  const params = useSearchParams();
  const premise = params.get("premise") ?? "";
  const query = params.toString();

  // A seed arrives only when an Opportunity was sent here (via URL). Stable id
  // per param-set so CopilotPanel applies it once and re-applies on a new pick.
  const seed = useMemo<CopilotSeed | null>(() => {
    if (!premise) return null;
    return {
      premise,
      genre: params.get("genre") || "fantasy",
      language: params.get("language") || "en",
      workingTitle: params.get("title") || "",
      seedId: hashNum(query),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  const tab = getStudioTab("copilot");
  return (
    <>
      <TabHeader icon={tab.icon} title={tab.title} subtitle={tab.subtitle} />
      <CopilotPanel seed={seed} />
    </>
  );
}

export default function CopilotPage() {
  return (
    <Suspense>
      <CopilotContent />
    </Suspense>
  );
}
