"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { useRef, type ReactNode } from "react";

import { cn } from "@/lib/utils";

export function GlowCardGrid({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3", className)}>
      {children}
    </div>
  );
}

export interface GlowCardProps {
  name: string;
  handle?: string;
  /** Profile mode: round avatar image. */
  avatar?: string;
  /** Video mode: 16:9 thumbnail. */
  thumb?: string;
  /** Small corner label (e.g. duration or views). */
  meta?: string;
  href?: string;
  index?: number;
}

/** Spotlight-glow card that tracks the cursor. Profile mode (avatar) or video mode (thumb). */
export function GlowCard({ name, handle, avatar, thumb, meta, href, index = 0 }: GlowCardProps) {
  const ref = useRef<HTMLDivElement>(null);

  const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${e.clientX - r.left}px`);
    el.style.setProperty("--my", `${e.clientY - r.top}px`);
  };

  const body = (
    <motion.div
      ref={ref}
      onMouseMove={onMove}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1], delay: (index % 12) * 0.04 }}
      whileHover={{ y: -4 }}
      className="group/glow relative h-full overflow-hidden rounded-xl border border-border bg-card"
    >
      {/* cursor spotlight */}
      <div
        aria-hidden
        className="pointer-events-none absolute -inset-px z-10 opacity-0 transition-opacity duration-300 group-hover/glow:opacity-100"
        style={{
          background:
            "radial-gradient(240px circle at var(--mx, 50%) var(--my, 50%), color-mix(in oklab, var(--primary) 22%, transparent), transparent 60%)",
        }}
      />
      {/* ring that lights up */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 z-20 rounded-xl ring-1 ring-inset ring-transparent transition duration-300 group-hover/glow:ring-foreground/20"
      />

      {thumb ? (
        <div className="relative">
          <div className="relative aspect-video overflow-hidden bg-muted">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={thumb}
              alt={name}
              loading="lazy"
              className="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover/glow:scale-105"
            />
            {meta && (
              <span className="absolute right-2 top-2 rounded bg-foreground/45 px-1.5 py-0.5 font-mono text-xs text-background tabular-nums">
                {meta}
              </span>
            )}
          </div>
          <div className="relative p-3">
            <h3 className="line-clamp-2 text-sm font-semibold text-card-foreground">{name}</h3>
            {handle && <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">{handle}</p>}
          </div>
        </div>
      ) : (
        <div className="relative flex items-center gap-3 p-4">
          {avatar && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={avatar}
              alt={name}
              loading="lazy"
              className="h-12 w-12 shrink-0 rounded-full border border-border object-cover"
            />
          )}
          <div className="min-w-0">
            <p className="truncate font-semibold text-card-foreground">{name}</p>
            {handle && <p className="truncate text-sm text-muted-foreground">{handle}</p>}
          </div>
        </div>
      )}
    </motion.div>
  );

  return href ? (
    <Link href={href} className="block h-full">
      {body}
    </Link>
  ) : (
    body
  );
}
