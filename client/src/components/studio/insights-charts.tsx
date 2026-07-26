"use client";

// evilcharts (Recharts) visualisations for the Insights tab. Both are single-
// series magnitude bar charts — one hue, glowing gradient, no legend needed —
// so there's no categorical-palette concern; the color is decorative, the height
// carries the value.

import { EvilBarChart } from "@/components/evilcharts/charts/recharts-bar-chart";
import { EvilLineChart } from "@/components/evilcharts/charts/recharts-line-chart";
import { type ChartConfig } from "@/components/evilcharts/ui/recharts-chart";
import { asRec, num, str } from "./ui";

/** Prettify a "horror/hi" segment key into "Horror · HI". */
function segmentLabel(segment: string): string {
  const [genre, lang] = segment.split("/");
  const g = genre ? genre.charAt(0).toUpperCase() + genre.slice(1) : segment;
  return lang ? `${g} · ${lang.toUpperCase()}` : g;
}

// Vibrant two-hue gradients — decorative on single-series magnitude charts, so
// no categorical-palette concern; the height carries the value.
const demandConfig = {
  listeners: {
    label: "Listeners",
    // top violet → bottom fuchsia/pink
    colors: { light: ["#9333ea", "#db2777"], dark: ["#a855f7", "#ec4899"] },
  },
} satisfies ChartConfig;

const saturationConfig = {
  saturation: {
    label: "Saturation",
    // top amber → bottom rose (warm, hot)
    colors: { light: ["#d97706", "#e11d48"], dark: ["#fbbf24", "#fb7185"] },
  },
} satisfies ChartConfig;

const retentionConfig = {
  retained: {
    label: "Listeners retained",
    // cyan → violet gradient stroke along the line
    colors: { light: ["#0891b2", "#7c3aed"], dark: ["#22d3ee", "#a855f7"] },
  },
} satisfies ChartConfig;

// Two-series: violet + rose — validated CVD-safe (ΔE 24.2) and in the lightness
// band, plus a legend and dots as secondary encoding.
const trendConfig = {
  completion: {
    label: "Completion",
    colors: { light: ["#7c3aed"], dark: ["#8b5cf6"] },
  },
  dropoff: {
    label: "Drop-off",
    colors: { light: ["#e11d48"], dark: ["#f43f5e"] },
  },
} satisfies ChartConfig;

/** Completion vs drop-off across the top segments — a two-line comparison. */
export function DemandTrendChart({ segments }: { segments: unknown[] }) {
  const data = segments
    .map(asRec)
    .map((row) => ({
      segment: segmentLabel(str(row.segment)),
      completion: Math.round(num(row.completion_rate) * 100),
      dropoff: Math.round(num(row.drop_off_rate) * 100),
      listeners: num(row.unique_listeners ?? row.plays),
    }))
    .filter((row) => row.listeners > 0)
    .sort((a, b) => b.listeners - a.listeners)
    .slice(0, 10);

  if (data.length < 2) return null;

  return (
    <div className="h-64 w-full">
      <EvilLineChart data={data} config={trendConfig} className="h-full w-full" xDataKey="segment">
        <EvilLineChart.Grid />
        <EvilLineChart.XAxis
          dataKey="segment"
          tickFormatter={(v: string) => v.split(" · ")[0].slice(0, 6)}
        />
        <EvilLineChart.Legend isClickable />
        <EvilLineChart.Tooltip />
        <EvilLineChart.Line dataKey="completion" strokeVariant="solid" curveType="monotone" glowing isClickable>
          <EvilLineChart.Dot variant="border" />
          <EvilLineChart.ActiveDot variant="colored-border" />
        </EvilLineChart.Line>
        <EvilLineChart.Line dataKey="dropoff" strokeVariant="solid" curveType="monotone" glowing isClickable>
          <EvilLineChart.Dot variant="border" />
          <EvilLineChart.ActiveDot variant="colored-border" />
        </EvilLineChart.Line>
      </EvilLineChart>
    </div>
  );
}

/** Retention over playback progress — a genuine over-time curve (line chart). */
export function RetentionChart({ curve }: { curve: unknown[] }) {
  const data = curve
    .map(asRec)
    .map((p, i) => ({
      point: `${Math.round(num(p.decile, i + 1) * 10)}%`,
      retained: Math.round(num(p.retained_ratio ?? p.retained ?? p.share) * 100),
    }));

  if (data.length < 2) return null;

  return (
    <div className="h-56 w-full">
      <EvilLineChart data={data} config={retentionConfig} className="h-full w-full" xDataKey="point">
        <EvilLineChart.Grid />
        <EvilLineChart.XAxis dataKey="point" />
        <EvilLineChart.Tooltip />
        <EvilLineChart.Line dataKey="retained" strokeVariant="solid" curveType="monotone" glowing>
          <EvilLineChart.Dot variant="border" />
          <EvilLineChart.ActiveDot variant="colored-border" />
        </EvilLineChart.Line>
      </EvilLineChart>
    </div>
  );
}

/** Top segments by audience size — where the demand actually is. */
export function DemandChart({ segments }: { segments: unknown[] }) {
  const data = segments
    .map(asRec)
    .map((row) => ({
      segment: segmentLabel(str(row.segment)),
      listeners: num(row.unique_listeners ?? row.plays),
    }))
    .filter((row) => row.listeners > 0)
    .sort((a, b) => b.listeners - a.listeners)
    .slice(0, 8);

  if (!data.length) return null;

  return (
    <div className="h-72 w-full">
      <EvilBarChart data={data} config={demandConfig} className="h-full w-full">
        <EvilBarChart.Grid />
        <EvilBarChart.XAxis
          dataKey="segment"
          tickFormatter={(v: string) => v.split(" · ")[0].slice(0, 8)}
        />
        <EvilBarChart.Tooltip />
        <EvilBarChart.Bar dataKey="listeners" variant="gradient" glowing radius={6} />
      </EvilBarChart>
    </div>
  );
}

/** Over-supplied narrative patterns — saturation index per pattern. */
export function SaturationChart({ patterns }: { patterns: unknown[] }) {
  const data = patterns
    .map(asRec)
    .map((row) => ({
      pattern: str(row.narrative_pattern ?? row.pattern, "pattern"),
      saturation: Number(num(row.saturation_index).toFixed(2)),
    }))
    .filter((row) => row.saturation > 0)
    .sort((a, b) => b.saturation - a.saturation)
    .slice(0, 8);

  if (!data.length) return null;

  return (
    <div className="h-64 w-full">
      <EvilBarChart data={data} config={saturationConfig} className="h-full w-full">
        <EvilBarChart.Grid />
        <EvilBarChart.XAxis
          dataKey="pattern"
          tickFormatter={(v: string) => v.slice(0, 10)}
        />
        <EvilBarChart.Tooltip />
        <EvilBarChart.Bar dataKey="saturation" variant="gradient" glowing radius={6} />
      </EvilBarChart>
    </div>
  );
}
