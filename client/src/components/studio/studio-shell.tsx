"use client";

import { BarChart3, Lightbulb, PenLine, Sparkles, Upload } from "lucide-react";
import { useRef, useState, type ComponentType } from "react";

import { SiteHeader } from "@/components/site-header";
import { useAuth } from "@/hooks/api/use-auth";
import { CopilotPanel } from "./copilot-panel";
import { InsightsPanel } from "./insights-panel";
import { OpportunitiesPanel } from "./opportunities-panel";
import { PerformancePanel } from "./performance-panel";
import { UploadPanel } from "./upload-panel";
import { Card } from "./ui";

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

const TABS: { id: TabId; label: string; icon: ComponentType<{ className?: string }> }[] = [
  { id: "opportunities", label: "Opportunities", icon: Lightbulb },
  { id: "performance", label: "Performance", icon: BarChart3 },
  { id: "upload", label: "Upload", icon: Upload },
  { id: "copilot", label: "Copilot", icon: PenLine },
  { id: "insights", label: "Insights", icon: Sparkles },
];

/** Creator Studio — demand intelligence, performance, upload, copilot, insights. */
export function StudioShell() {
  const { isAuthenticated } = useAuth();
  const [tab, setTab] = useState<TabId>("opportunities");
  const [copilotSeed, setCopilotSeed] = useState<CopilotSeed | null>(null);
  const seedCounter = useRef(0);

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
            What to make, and how it’s doing
          </h1>
        </header>

        {!isAuthenticated ? (
          <Card className="text-center">
            <p className="font-semibold text-foreground">Sign in to open your studio</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Use “Sign in” in the top-right. Opportunities, performance and uploads are tied
              to your creator account.
            </p>
          </Card>
        ) : (
          <>
            <nav className="mb-6 flex flex-wrap gap-2">
              {TABS.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setTab(id)}
                  className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                    tab === id
                      ? "bg-primary text-primary-foreground"
                      : "border border-white/10 text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </button>
              ))}
            </nav>

            {tab === "opportunities" && <OpportunitiesPanel onWriteThis={sendToCopilot} />}
            {tab === "performance" && <PerformancePanel />}
            {tab === "upload" && <UploadPanel />}
            {tab === "copilot" && <CopilotPanel seed={copilotSeed} />}
            {tab === "insights" && <InsightsPanel />}
          </>
        )}
      </main>
    </div>
  );
}
