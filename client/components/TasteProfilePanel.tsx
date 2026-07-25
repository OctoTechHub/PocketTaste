import type { TasteProfile } from "@/lib/types";
import { genreColor } from "@/lib/visuals";

function AffinityBars({
  title,
  data,
  colorFor,
}: {
  title: string;
  data: Record<string, number>;
  colorFor?: (k: string) => string;
}) {
  const entries = Object.entries(data)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);
  if (entries.length === 0) return null;
  return (
    <div>
      <p className="mb-1.5 text-xs uppercase tracking-wide text-muted">{title}</p>
      <div className="space-y-1.5">
        {entries.map(([k, v]) => (
          <div key={k} className="flex items-center gap-2">
            <span className="w-24 shrink-0 truncate text-xs text-foreground">{k}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/5">
              <div
                className="h-full rounded-full"
                style={{ width: `${Math.round(v * 100)}%`, background: colorFor?.(k) ?? "#7c5cff" }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Sidebar showing the derived taste profile — the "why" behind the feed. */
export function TasteProfilePanel({ profile }: { profile: TasteProfile | null }) {
  if (!profile) return null;
  return (
    <aside className="space-y-5 rounded-2xl border border-border bg-surface/60 p-5">
      <div>
        <h3 className="text-sm font-semibold text-foreground">Taste profile</h3>
        <p className="mt-0.5 text-xs text-muted">
          Learned from {profile.eventCount} signals · {profile.coinSpend} coins spent
        </p>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <Stat label="Top genre" value={profile.topGenre} />
        <Stat label="Tone" value={profile.topTone} />
        <Stat label="Language" value={profile.topLanguage} />
      </div>
      <AffinityBars title="Genre affinity" data={profile.genreAffinity} colorFor={genreColor} />
      <AffinityBars title="Tone affinity" data={profile.toneAffinity} />
      <div className="flex items-center justify-between rounded-lg bg-surface-2/50 px-3 py-2 text-xs">
        <span className="text-muted">Preferred episode length</span>
        <span className="font-mono text-foreground">
          ~{Math.round(profile.avgPreferredEpisodeMinutes)} min
        </span>
      </div>
    </aside>
  );
}

function Stat({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="rounded-lg bg-surface-2/50 px-2 py-2">
      <p className="truncate text-sm font-semibold capitalize text-foreground">{value ?? "—"}</p>
      <p className="text-[10px] uppercase tracking-wide text-muted">{label}</p>
    </div>
  );
}
