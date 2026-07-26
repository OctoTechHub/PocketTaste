"use client";

/**
 * The shared visual language of Blend.
 *
 * Two listeners, two colours. Every mixed value on this surface is produced with
 * `color-mix(in oklab, ...)` at a percentage taken straight from the algorithm's
 * `lean` output — so the colour of a row is not a decorative choice, it is the
 * attribution rendered. A row that is 70% one person's taste is 70% their hue.
 */

export const YOU = "oklch(0.72 0.19 32)"; // ember
export const THEM = "oklch(0.70 0.15 258)"; // indigo

/** `lean` is -1 (entirely you) .. +1 (entirely them). Returns 0..100 toward them. */
export function leanToPercent(lean: number): number {
  return Math.round(((Math.max(-1, Math.min(1, lean)) + 1) / 2) * 100);
}

/** The colour an item earns from its own lean value. */
export function leanColor(lean: number): string {
  return `color-mix(in oklab, ${YOU} ${100 - leanToPercent(lean)}%, ${THEM})`;
}

export function ownerColor(owner: string, members: { user_id: string }[]): string {
  if (owner === "shared") return `color-mix(in oklab, ${YOU} 50%, ${THEM})`;
  return owner === members[0]?.user_id ? YOU : THEM;
}

/**
 * The match, drawn as the thing it actually is: two sets and their intersection.
 *
 * A percentage in large type would say the same number, but a Venn says what the
 * number *means* — that these are two separate tastes with a measurable shared
 * region. The discs move apart as the match falls, so a weak blend looks weak.
 */
export function MatchVenn({
  match,
  youLabel,
  themLabel,
  size = 168,
}: {
  match: number;
  youLabel: string;
  themLabel: string;
  size?: number;
}) {
  const radius = size * 0.28;
  // At match=1 the discs sit on top of each other; at 0 they barely touch.
  const separation = radius * (2 - 1.05 * Math.min(1, Math.max(0, match)));
  const centre = size / 2;
  const percent = Math.round(match * 100);

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={`Taste match ${percent} percent between ${youLabel} and ${themLabel}`}
      >
        <defs>
          <clipPath id="blend-left">
            <circle cx={centre - separation / 2} cy={centre} r={radius} />
          </clipPath>
        </defs>
        <circle
          cx={centre - separation / 2}
          cy={centre}
          r={radius}
          fill={YOU}
          fillOpacity={0.22}
          stroke={YOU}
          strokeOpacity={0.55}
        />
        <circle
          cx={centre + separation / 2}
          cy={centre}
          r={radius}
          fill={THEM}
          fillOpacity={0.22}
          stroke={THEM}
          strokeOpacity={0.55}
        />
        {/* The intersection, drawn by clipping one disc to the other. */}
        <g clipPath="url(#blend-left)">
          <circle
            cx={centre + separation / 2}
            cy={centre}
            r={radius}
            fill={`color-mix(in oklab, ${YOU} 50%, ${THEM})`}
            fillOpacity={0.75}
          />
        </g>
      </svg>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-black tabular-nums tracking-tighter text-white">
          {percent}
          <span className="text-lg font-bold">%</span>
        </span>
        <span className="text-[10px] font-medium uppercase tracking-[0.18em] text-white/55">
          match
        </span>
      </div>
    </div>
  );
}

/**
 * Where one story sits between two people. The marker position is the raw `lean`
 * value; nothing here is smoothed or rounded for looks.
 */
export function LeanMeter({
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
  const percent = leanToPercent(lean);
  return (
    <div
      className="flex items-center gap-2"
      role="img"
      aria-label={`${youLabel} scores this ${Math.round(youScore * 100)} percent, ${themLabel} ${Math.round(themScore * 100)} percent`}
    >
      <span className="w-8 text-right text-[10px] font-semibold tabular-nums text-white/50">
        {Math.round(youScore * 100)}
      </span>
      <div className="relative h-1 flex-1 overflow-hidden rounded-full">
        <div
          className="absolute inset-0"
          style={{ background: `linear-gradient(90deg, ${YOU}, ${THEM})`, opacity: 0.3 }}
        />
        <div
          className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-black/50 transition-[left] duration-500"
          style={{ left: `${percent}%`, background: leanColor(lean) }}
        />
      </div>
      <span className="w-8 text-[10px] font-semibold tabular-nums text-white/50">
        {Math.round(themScore * 100)}
      </span>
    </div>
  );
}
