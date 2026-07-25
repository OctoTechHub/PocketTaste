"use client";

// Small presentational primitives shared by the Studio and Admin surfaces, plus
// safe accessors for the loosely-typed (JsonRecord) API payloads.

import type { ReactNode } from "react";

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

// --- layout -----------------------------------------------------------------

export function Card({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-white/10 bg-white/[0.03] p-5",
        className,
      )}
    >
      {children}
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

export function StatTile({
  label,
  value,
  hint,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums text-foreground">{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
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
  const width = `${Math.max(0, Math.min(1, value)) * 100}%`;
  return (
    <span className="block h-1.5 w-full overflow-hidden rounded-full bg-white/10">
      <span
        className={cn("block h-full rounded-full", tone === "warn" ? "bg-amber-400" : "bg-primary")}
        style={{ width }}
      />
    </span>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <Card className="text-center">
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

/** Provenance banner — never lets a synthetic figure read as real audience data. */
export function ProvenanceNote({ provenance, notice }: { provenance?: unknown; notice?: unknown }) {
  const p = str(provenance);
  if (!p) return null;
  const real = p === "real";
  return (
    <div
      className={cn(
        "rounded-lg border px-3 py-2 text-xs",
        real
          ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-200"
          : "border-amber-500/20 bg-amber-500/10 text-amber-200",
      )}
    >
      <span className="font-semibold">provenance: {p}</span>
      {notice ? <span className="opacity-80"> — {str(notice)}</span> : null}
    </div>
  );
}
