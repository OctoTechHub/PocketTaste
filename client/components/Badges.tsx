import type { CandidateSource } from "@/lib/types";
import { genreColor } from "@/lib/visuals";

export function Chip({
  children,
  color,
  subtle,
}: {
  children: React.ReactNode;
  color?: string;
  subtle?: boolean;
}) {
  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
      style={{
        color: color ?? "var(--muted)",
        background: subtle ? "transparent" : `${color ?? "#7c5cff"}1f`,
        border: `1px solid ${color ?? "var(--border)"}33`,
      }}
    >
      {children}
    </span>
  );
}

export function GenreChip({ genre }: { genre: string }) {
  return <Chip color={genreColor(genre)}>{genre}</Chip>;
}

const SOURCE_LABEL: Record<CandidateSource, string> = {
  content: "taste-match",
  collaborative: "co-listened",
  popularity: "trending",
  query: "search",
};

export function SourceTag({ source }: { source: CandidateSource }) {
  return (
    <span className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted">
      {SOURCE_LABEL[source]}
    </span>
  );
}

export function ReasonBadge({ reason }: { reason: string | null }) {
  if (!reason) return null;
  return (
    <p className="mt-2 text-xs leading-snug text-muted">
      <span className="mr-1 text-accent">✦</span>
      {reason}
    </p>
  );
}
