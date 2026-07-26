"use client";

import { InsightsPanel } from "@/components/studio/insights-panel";
import { getStudioTab } from "@/components/studio/tabs";
import { TabHeader } from "@/components/studio/ui";

export default function InsightsPage() {
  const tab = getStudioTab("insights");
  return (
    <>
      <TabHeader icon={tab.icon} title={tab.title} subtitle={tab.subtitle} />
      <InsightsPanel />
    </>
  );
}
