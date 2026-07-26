"use client";

/**
 * Blend's data colours.
 *
 * The page chrome is the app's own — `Card`, `text-primary`, `muted-foreground`, the
 * same radii and borders as Studio and Admin. What Blend adds is a two-identity
 * colour system, and it exists only where it carries meaning: every mixed value is
 * produced with `color-mix(in oklab, ...)` at a percentage taken from the algorithm's
 * `lean` output, so a row that is 70% one person's taste is 70% their hue. These two
 * hues are never used for chrome, and the app's primary is never used for data.
 */

// Two-person identity colours. Darkened for the light theme: the old L≈0.71
// pair was tuned to glow on a dark surface and only reached 2.7:1 against paper
// (and the same against the white initials sitting on them). At L≈0.53 both
// clear 5:1 as fills, stay far apart in hue (ember vs indigo — the safest pair
// for colour-vision deficiency), and still read as two distinct people.
export const YOU = "oklch(0.55 0.17 32)"; // ember
export const THEM = "oklch(0.52 0.15 262)"; // indigo
export const SHARED_COLOR = `color-mix(in oklab, ${YOU} 50%, ${THEM})`;

/** `lean` is -1 (entirely you) .. +1 (entirely them). Returns 0..100 toward them. */
export function leanToPercent(lean: number): number {
  return Math.round(((Math.max(-1, Math.min(1, lean)) + 1) / 2) * 100);
}

export function leanColor(lean: number): string {
  return `color-mix(in oklab, ${YOU} ${100 - leanToPercent(lean)}%, ${THEM})`;
}

export function initials(name: string): string {
  return name.trim().slice(0, 1).toUpperCase() || "?";
}

/**
 * Two listeners as overlapping discs — the one borrowed gesture, because it is the
 * clearest way anyone has drawn "two tastes and their shared part".
 *
 * Separation is driven by the match rather than fixed, so a weak blend reads as weak
 * before the number is parsed. `settled` drives the entrance: the discs start apart
 * and close to their real position once the result lands, which is the whole
 * blending moment. Intrinsic size is fixed so the header never reflows.
 */
export function BlendMark({
  match,
  youLabel,
  themLabel,
  size = 116,
  settled = true,
}: {
  match: number;
  youLabel: string;
  themLabel: string;
  size?: number;
  settled?: boolean;
}) {
  const radius = size * 0.29;
  const target = radius * (2 - 1.05 * Math.min(1, Math.max(0, match)));
  const separation = settled ? target : radius * 2.1;
  const centre = size / 2;

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className="shrink-0"
      role="img"
      aria-label={`${Math.round(match * 100)} percent taste match between ${youLabel} and ${themLabel}`}
    >
      <defs>
        <clipPath id="blendmark-clip">
          <circle cx={centre - separation / 2} cy={centre} r={radius} />
        </clipPath>
      </defs>
      <g
        style={{
          transition: "opacity 400ms ease-out",
          opacity: settled ? 1 : 0.55,
        }}
      >
        <circle cx={centre - separation / 2} cy={centre} r={radius} fill={YOU} fillOpacity={0.85} />
        <circle cx={centre + separation / 2} cy={centre} r={radius} fill={THEM} fillOpacity={0.85} />
        <g clipPath="url(#blendmark-clip)">
          <circle cx={centre + separation / 2} cy={centre} r={radius} fill={SHARED_COLOR} />
        </g>
      </g>
      {settled ? (
        <text
          x={centre}
          y={centre}
          textAnchor="middle"
          dominantBaseline="central"
          className="fill-white font-black"
          style={{ fontSize: size * 0.21, letterSpacing: "-0.03em" }}
        >
          {Math.round(match * 100)}%
        </text>
      ) : null}
    </svg>
  );
}

/** Where one story sits between two people. Position is the raw `lean`, unrounded. */
export function LeanBar({
  lean,
  youScore,
  themScore,
  youLabel,
  themLabel,
}: {
  lean: number;
  youScore: number;
  themScore: number;
  youLabel: string;
  themLabel: string;
}) {
  return (
    <div
      className="flex items-center gap-2"
      role="img"
      aria-label={`${youLabel} ${Math.round(youScore * 100)} percent, ${themLabel} ${Math.round(themScore * 100)} percent`}
    >
      <span className="w-7 text-right text-[11px] font-semibold tabular-nums text-muted-foreground">
        {Math.round(youScore * 100)}
      </span>
      <span className="relative h-[3px] w-full min-w-[72px] max-w-[128px] rounded-full bg-muted">
        <span
          className="absolute top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{ left: `${leanToPercent(lean)}%`, background: leanColor(lean) }}
        />
      </span>
      <span className="w-7 text-[11px] font-semibold tabular-nums text-muted-foreground">
        {Math.round(themScore * 100)}
      </span>
    </div>
  );
}
