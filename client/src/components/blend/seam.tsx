"use client";

/**
 * Blend's data colours and the small marks built from them.
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

export type Rgb = readonly [number, number, number];

/**
 * The same two colours as sRGB triplets, for `<canvas>`.
 *
 * Canvas has no `color-mix()` and no reliable way to read a computed `oklch()`
 * back out of the DOM — Chrome hands the wide-gamut string straight back rather
 * than an `rgb()` you could parse. These are the converted values, and they are
 * the *only* place the two colours are duplicated. Change one, change both.
 */
export const YOU_RGB: Rgb = [193, 63, 41];
export const THEM_RGB: Rgb = [54, 100, 190];

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
 * One listener, as the end of a strand.
 *
 * The dot is the identity colour at full strength — it is the only place either
 * hue appears as a solid fill next to a name, which is what teaches the legend
 * for every lean marker further down the page.
 */
export function StrandEnd({
  name,
  colour,
  meta,
  align = "left",
}: {
  name: string;
  colour: string;
  meta?: string;
  align?: "left" | "right";
}) {
  const right = align === "right";
  return (
    <div
      className={`flex min-w-0 items-center gap-2.5 ${right ? "flex-row-reverse text-right" : ""}`}
    >
      <span
        aria-hidden
        className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-[13px] font-black text-white ring-2 ring-card"
        style={{ background: colour }}
      >
        {initials(name)}
      </span>
      <span className="min-w-0">
        <span className="block truncate text-sm font-bold text-foreground">{name}</span>
        {meta ? (
          <span className="block truncate text-[11px] text-muted-foreground">{meta}</span>
        ) : null}
      </span>
    </div>
  );
}

/**
 * Two listeners as overlapping discs — kept for the compact places the helix is
 * too wide for, and because it is still the clearest static picture of "two
 * tastes and their shared part". Separation is driven by the match, so a weak
 * blend reads as weak before the number is parsed.
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
      <g style={{ transition: "opacity 400ms ease-out", opacity: settled ? 1 : 0.55 }}>
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

/**
 * A single base pair, seen end-on: the row's lean as a two-tone bar.
 *
 * This replaces the plain accent dot the rows used to carry. A dot could only say
 * *which* listener a story leaned to; the split says *how far*, in the same
 * gradient language as the helix above it, and it survives being 3px wide.
 */
export function BasePair({ lean, shared }: { lean: number; shared: boolean }) {
  const split = shared ? 50 : leanToPercent(lean);
  return (
    <span
      aria-hidden
      className="block h-6 w-[3px] shrink-0 rounded-full"
      style={{
        background: `linear-gradient(to bottom, ${YOU} 0%, ${YOU} ${Math.max(0, split - 14)}%, ${SHARED_COLOR} ${split}%, ${THEM} ${Math.min(100, split + 14)}%, ${THEM} 100%)`,
      }}
    />
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
        {/* Strand ends, so the rail reads as the span between two people. */}
        <span
          className="absolute left-0 top-1/2 h-1.5 w-1.5 -translate-x-px -translate-y-1/2 rounded-full"
          style={{ background: YOU, opacity: 0.45 }}
        />
        <span
          className="absolute right-0 top-1/2 h-1.5 w-1.5 translate-x-px -translate-y-1/2 rounded-full"
          style={{ background: THEM, opacity: 0.45 }}
        />
        <span
          className="absolute top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-card"
          style={{ left: `${leanToPercent(lean)}%`, background: leanColor(lean) }}
        />
      </span>
      <span className="w-7 text-[11px] font-semibold tabular-nums text-muted-foreground">
        {Math.round(themScore * 100)}
      </span>
    </div>
  );
}
