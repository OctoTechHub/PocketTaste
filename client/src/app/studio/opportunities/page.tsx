"use client";

import { useRouter } from "next/navigation";

import { OpportunitiesPanel } from "@/components/studio/opportunities-panel";
import { getStudioTab } from "@/components/studio/tabs";
import { TabHeader } from "@/components/studio/ui";
import type { CopilotSeed } from "@/components/studio/studio-shell";

export default function OpportunitiesPage() {
  const router = useRouter();
  const tab = getStudioTab("opportunities");

  const onWriteThis = (seed: Omit<CopilotSeed, "seedId">) => {
    const q = new URLSearchParams({
      premise: seed.premise,
      genre: seed.genre,
      language: seed.language,
      title: seed.workingTitle,
    });
    router.push(`/studio/copilot?${q.toString()}`);
  };

  return (
    <>
      <TabHeader icon={tab.icon} title={tab.title} subtitle={tab.subtitle} />
      <OpportunitiesPanel onWriteThis={onWriteThis} />
    </>
  );
}
