"use client";

import { getStudioTab } from "@/components/studio/tabs";
import { TabHeader } from "@/components/studio/ui";
import { UploadPanel } from "@/components/studio/upload-panel";

export default function UploadPage() {
  const tab = getStudioTab("upload");
  return (
    <>
      <TabHeader icon={tab.icon} title={tab.title} subtitle={tab.subtitle} />
      <UploadPanel />
    </>
  );
}
