import type { DiscoveryIntent } from "@/lib/types";
import { Chip, GenreChip } from "./Badges";

/** Shows how the engine understood a natural-language query. */
export function IntentChips({ intent }: { intent: DiscoveryIntent }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="text-xs uppercase tracking-wide text-muted">Understood as</span>
      {intent.language && <Chip color="#60a5fa">{intent.language}</Chip>}
      {intent.genres.map((g) => (
        <GenreChip key={g} genre={g} />
      ))}
      {intent.tones.map((t) => (
        <Chip key={t} color="#a78bfa">
          {t}
        </Chip>
      ))}
      {intent.pacing && <Chip color="#34d399">{intent.pacing}</Chip>}
      {intent.maxEpisodeMinutes && <Chip>≤ {intent.maxEpisodeMinutes}m</Chip>}
      {intent.excludeGenres.map((g) => (
        <Chip key={g} color="#ef4444">
          no {g}
        </Chip>
      ))}
    </div>
  );
}
