"use client";

import { PerformancePanel } from "@/components/studio/performance-panel";
import { getStudioTab } from "@/components/studio/tabs";
import { TabHeader } from "@/components/studio/ui";

export default function PerformancePage() {
  const tab = getStudioTab("performance");
  return (
    <>
      <TabHeader icon={tab.icon} title={tab.title} subtitle={tab.subtitle} />
      <PerformancePanel />
    </>
  );
}
