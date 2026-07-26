import { BarChart3, Lightbulb, PenLine, Sparkles, Upload } from "lucide-react";
import type { ComponentType } from "react";

export type StudioTab = {
  slug: string;
  href: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  title: string;
  subtitle: string;
};

/** One entry per Studio section — drives the nav (layout) and the per-page header. */
export const STUDIO_TABS: StudioTab[] = [
  {
    slug: "opportunities",
    href: "/studio/opportunities",
    label: "Opportunities",
    icon: Lightbulb,
    title: "What should I make next?",
    subtitle: "Demand gaps ranked for you — write-more vs write-better.",
  },
  {
    slug: "performance",
    href: "/studio/performance",
    label: "Performance",
    icon: BarChart3,
    title: "How are my stories doing?",
    subtitle: "Per-story retention, drop-off and weakest episodes.",
  },
  {
    slug: "upload",
    href: "/studio/upload",
    label: "Upload",
    icon: Upload,
    title: "Publish a new story",
    subtitle: "Screened for duplication before it goes live.",
  },
  {
    slug: "copilot",
    href: "/studio/copilot",
    label: "Copilot",
    icon: PenLine,
    title: "Draft with the story copilot",
    subtitle: "Screened, demand-anchored outlines and scenes.",
  },
  {
    slug: "insights",
    href: "/studio/insights",
    label: "Insights",
    icon: Sparkles,
    title: "Where the audience is",
    subtitle: "Platform demand, saturation and evidence-backed briefs.",
  },
];

export function getStudioTab(slug: string): StudioTab {
  return STUDIO_TABS.find((t) => t.slug === slug) ?? STUDIO_TABS[0];
}
