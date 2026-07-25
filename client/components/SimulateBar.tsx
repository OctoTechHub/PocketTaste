"use client";

import { useState } from "react";
import { api } from "@/lib/apiClient";
import type { EventType, Series } from "@/lib/types";

const ACTIONS: { type: EventType; label: string; coins?: boolean; tone: string }[] = [
  { type: "play", label: "▶ Play episode", tone: "#60a5fa" },
  { type: "complete_series", label: "✓ Binge whole series", tone: "#34d399" },
  { type: "coin_unlock", label: "🪙 Unlock with coins", coins: true, tone: "#f0a500" },
  { type: "drop", label: "✕ Drop it", tone: "#ef4444" },
];

/**
 * Logs real behavior events for the current user, then triggers a feed refresh so
 * the "in-session adaptation" is visible live — the core demo moment.
 */
export function SimulateBar({
  userId,
  series,
  onLogged,
}: {
  userId: string;
  series: Series;
  onLogged: () => void;
}) {
  const [busy, setBusy] = useState<EventType | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  const fire = async (type: EventType, coins?: boolean) => {
    setBusy(type);
    try {
      await api.logEvent({
        userId,
        seriesId: series.id,
        type,
        coins: coins ? series.coinPriceApprox : undefined,
        completionPct: type === "complete_series" ? 1 : type === "drop" ? 0.1 : undefined,
      });
      setFlash(`Logged: ${type.replace("_", " ")} → feed updating…`);
      onLogged();
      setTimeout(() => setFlash(null), 2500);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <p className="mb-2 text-xs uppercase tracking-wide text-muted">
        Simulate listening — watch the feed adapt
      </p>
      <div className="flex flex-wrap gap-2">
        {ACTIONS.map((a) => (
          <button
            key={a.type}
            disabled={busy !== null}
            onClick={() => fire(a.type, a.coins)}
            className="rounded-lg border px-3 py-1.5 text-xs font-medium transition hover:brightness-125 disabled:opacity-40"
            style={{ borderColor: `${a.tone}55`, color: a.tone, background: `${a.tone}14` }}
          >
            {busy === a.type ? "…" : a.label}
          </button>
        ))}
      </div>
      {flash && <p className="mt-2 text-xs text-accent">{flash}</p>}
    </div>
  );
}
