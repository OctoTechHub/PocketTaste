"use client";

import { AnimatePresence, motion } from "motion/react";
import { BarChart3, Lightbulb, PenLine, Sparkles, Upload } from "lucide-react";
import { useRef, useState, type ComponentType } from "react";

import { SiteHeader } from "@/components/site-header";
import { useAuth } from "@/hooks/api/use-auth";
import { CopilotPanel } from "./copilot-panel";
import { InsightsPanel } from "./insights-panel";
import { OpportunitiesPanel } from "./opportunities-panel";
import { PerformancePanel } from "./performance-panel";
import { UploadPanel } from "./upload-panel";
import { Card, TabHeader } from "./ui";

type TabId = "opportunities" | "performance" | "upload" | "copilot" | "insights";

export type CopilotSeed = {
  premise: string;
  genre: string;
  language: string;
  workingTitle: string;
  /** Bumped on every selection so CopilotPanel can tell two seeds with the same
   * text apart and re-apply the prefill even if the user picks the same row twice. */
  seedId: number;
};

type Tab = {
  id: TabId;
  label: string;
  icon: ComponentType<{ className?: string }>;
  title: string;
  subtitle: string;
};

const TABS: Tab[] = [
  {
    id: "opportunities",
    label: "Opportunities",
    icon: Lightbulb,
    title: "What should I make next?",
    subtitle: "Demand gaps ranked for you — write-more vs write-better.",
  },
  {
    id: "performance",
    label: "Performance",
    icon: BarChart3,
    title: "How are my stories doing?",
    subtitle: "Per-story retention, drop-off and weakest episodes.",
  },
  {
    id: "upload",
    label: "Upload",
    icon: Upload,
    title: "Publish a new story",
    subtitle: "Screened for duplication before it goes live.",
  },
  {
    id: "copilot",
    label: "Copilot",
    icon: PenLine,
    title: "Draft with the story copilot",
    subtitle: "Screened, demand-anchored outlines and scenes.",
  },
  {
    id: "insights",
    label: "Insights",
    icon: Sparkles,
    title: "Where the audience is",
    subtitle: "Platform demand, saturation and evidence-backed briefs.",
  },
];

/** Creator Studio — demand intelligence, performance, upload, copilot, insights. */
export function StudioShell() {
  const { isAuthenticated, account } = useAuth();
  const [tab, setTab] = useState<TabId>("opportunities");
  const [copilotSeed, setCopilotSeed] = useState<CopilotSeed | null>(null);
  const seedCounter = useRef(0);
  const current = TABS.find((t) => t.id === tab)!;

  function sendToCopilot(seed: Omit<CopilotSeed, "seedId">) {
    seedCounter.current += 1;
    setCopilotSeed({ ...seed, seedId: seedCounter.current });
    setTab("copilot");
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main className="mx-auto max-w-6xl px-4 pb-20 pt-24 sm:px-8">
        <header className="mb-6">
          <p className="text-xs font-black uppercase tracking-[0.2em] text-primary">
            Creator Studio
          </p>
          <h1 className="mt-1 text-2xl font-bold sm:text-3xl">
            {account?.display_name ? `Welcome, ${account.display_name}` : "Your studio"}
          </h1>
        </header>

        {!isAuthenticated ? (
          <Card className="text-center" spotlight={false}>
            <p className="font-semibold text-foreground">Sign in to open your studio</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Use “Sign in” in the top-right. Opportunities, performance and uploads are tied
              to your creator account.
            </p>
          </Card>
        ) : (
          <>
            {/* Animated segmented tabs with a gliding indicator */}
            <nav className="mb-6 flex flex-wrap gap-2">
              {TABS.map(({ id, label, icon: Icon }) => {
                const active = tab === id;
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setTab(id)}
                    className={`relative inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                      active
                        ? "text-primary-foreground"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {active ? (
                      <motion.span
                        layoutId="studio-tab-pill"
                        className="absolute inset-0 -z-10 rounded-full bg-primary"
                        transition={{ type: "spring", stiffness: 480, damping: 38 }}
                      />
                    ) : (
                      <span className="absolute inset-0 -z-10 rounded-full border border-white/10" />
                    )}
                    <Icon className="h-4 w-4" />
                    {label}
                  </button>
                );
              })}
            </nav>

            <AnimatePresence mode="wait">
              <motion.section
                key={tab}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
              >
                <TabHeader icon={current.icon} title={current.title} subtitle={current.subtitle} />
                {tab === "opportunities" && <OpportunitiesPanel onWriteThis={sendToCopilot} />}
                {tab === "performance" && <PerformancePanel />}
                {tab === "upload" && <UploadPanel />}
                {tab === "copilot" && <CopilotPanel seed={copilotSeed} />}
                {tab === "insights" && <InsightsPanel />}
              </motion.section>
            </AnimatePresence>
          </>
        )}
      </main>
    </div>
  );
}
