"use client";

// Shared presentational primitives for the Studio + Admin surfaces. These wrap
// the React Bits components (SpotlightCard, CountUp, ShinyText) so every tab
// shares one interactive, consistent design language, plus safe accessors for
// the loosely-typed (JsonRecord) API payloads.

import { motion, useReducedMotion } from "motion/react";
import type { ComponentType, ReactNode } from "react";

import CountUp from "@/components/CountUp";
import ShinyText from "@/components/ShinyText";
import SpotlightCard from "@/components/SpotlightCard";
import { cn } from "@/lib/utils";

// --- safe accessors ---------------------------------------------------------

export type Rec = Record<string, unknown>;

export const asRec = (v: unknown): Rec => (v && typeof v === "object" ? (v as Rec) : {});
export const str = (v: unknown, fallback = ""): string =>
  typeof v === "string" ? v : v == null ? fallback : String(v);
export const num = (v: unknown, fallback = 0): number =>
  typeof v === "number" && Number.isFinite(v) ? v : fallback;
export const arr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
export const pct = (v: unknown): string =>
  v == null || typeof v !== "number" ? "—" : `${Math.round(v * 100)}%`;

/** A calm, user-facing message. Never leaks status codes, stack traces or
 *  endpoint paths into the UI — those belong in the console, not a demo. */
export function friendlyError(_err?: unknown, fallback = "Couldn’t load this just yet."): string {
  return fallback;
}

const SPOTLIGHT = "rgba(139, 140, 255, 0.14)" as const;

// --- motion reveal ----------------------------------------------------------

/** Fade + slide-up entrance. `index` staggers items in a grid/list. */
export function Reveal({
  children,
  index = 0,
  className,
}: {
  children: ReactNode;
  index?: number;
  className?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? { opacity: 0 } : { opacity: 0, y: 14 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1], delay: Math.min(index * 0.05, 0.4) }}
    >
      {children}
    </motion.div>
  );
}

// --- layout -----------------------------------------------------------------

/** Interactive spotlight card. Set `spotlight={false}` for a plain surface. */
export function Card({
  children,
  className,
  spotlight = true,
}: {
  children: ReactNode;
  className?: string;
  spotlight?: boolean;
}) {
  const cls = cn("rounded-2xl p-5", className);
  if (!spotlight) {
    return (
      <div className={cn("border border-white/10 bg-white/[0.03]", cls)}>{children}</div>
    );
  }
  return (
    <SpotlightCard className={cls} spotlightColor={SPOTLIGHT}>
      {children}
    </SpotlightCard>
  );
}

/** Consistent header for each Studio tab: icon + shimmering title + creator-POV subtitle. */
export function TabHeader({
  icon: Icon,
  title,
  subtitle,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="mb-6 flex items-center gap-3">
      <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
        <Icon className="h-5 w-5" />
      </span>
      <div>
        <ShinyText text={title} speed={4} className="text-xl font-bold" color="#e7e7ff" shineColor="#ffffff" />
        <p className="text-sm text-muted-foreground">{subtitle}</p>
      </div>
    </div>
  );
}

export function SectionTitle({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-4 flex items-start justify-between gap-4">
      <div>
        <h2 className="text-lg font-bold text-foreground">{title}</h2>
        {subtitle ? (
          <p className="mt-0.5 text-sm text-muted-foreground">{subtitle}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

/** KPI tile. A numeric `value` animates up with CountUp; strings render as-is. */
export function StatTile({
  label,
  value,
  suffix,
  hint,
}: {
  label: string;
  value: number | ReactNode;
  suffix?: string;
  hint?: string;
}) {
  return (
    <SpotlightCard className="rounded-xl p-4" spotlightColor={SPOTLIGHT}>
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums text-foreground">
        {typeof value === "number" ? (
          <>
            <CountUp to={value} separator="," duration={1.2} />
            {suffix}
          </>
        ) : (
          value
        )}
      </p>
      {hint ? <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p> : null}
    </SpotlightCard>
  );
}

export function Pill({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "good" | "warn" | "bad";
}) {
  const tones = {
    neutral: "bg-white/10 text-foreground",
    good: "bg-emerald-500/15 text-emerald-300",
    warn: "bg-amber-500/15 text-amber-300",
    bad: "bg-red-500/15 text-red-300",
  } as const;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}

/** Horizontal meter, 0..1. */
export function Meter({ value, tone = "primary" }: { value: number; tone?: "primary" | "warn" }) {
  const reduce = useReducedMotion();
  const width = `${Math.max(0, Math.min(1, value)) * 100}%`;
  return (
    <span className="block h-1.5 w-full overflow-hidden rounded-full bg-white/10">
      <motion.span
        className={cn("block h-full rounded-full", tone === "warn" ? "bg-amber-400" : "bg-primary")}
        initial={reduce ? { width } : { width: 0 }}
        whileInView={{ width }}
        viewport={{ once: true }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
      />
    </span>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <Card className="text-center" spotlight={false}>
      <p className="font-semibold text-foreground">{title}</p>
      {hint ? <p className="mt-1 text-sm text-muted-foreground">{hint}</p> : null}
    </Card>
  );
}

/** Collapsible pretty-printed JSON, for payload fields we don't render bespoke. */
export function JsonBlock({ data, label = "Raw response" }: { data: unknown; label?: string }) {
  return (
    <details className="rounded-xl border border-white/10 bg-black/30">
      <summary className="cursor-pointer select-none px-4 py-2 text-xs font-medium text-muted-foreground">
        {label}
      </summary>
      <pre className="max-h-96 overflow-auto px-4 pb-4 text-xs leading-relaxed text-foreground/80">
        {JSON.stringify(data, null, 2)}
      </pre>
    </details>
  );
}

const PROVENANCE_LABEL: Record<string, string> = {
  real: "Live audience data",
  synthetic_simulation: "Demo data · simulated listening",
  simulated_from_real_catalog: "Modeled from the real catalog",
  mixed: "Mixed live & modeled data",
};

/** Subtle, human-readable data-source chip. Keeps us honest about simulated
 *  figures without showing raw enum values in a demo. */
export function ProvenanceNote({ provenance }: { provenance?: unknown; notice?: unknown }) {
  const p = str(provenance);
  if (!p) return null;
  const real = p === "real";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
        real ? "bg-emerald-500/12 text-emerald-300" : "bg-white/8 text-muted-foreground",
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", real ? "bg-emerald-400" : "bg-amber-400")} />
      {PROVENANCE_LABEL[p] ?? "Audience data"}
    </span>
  );
}
