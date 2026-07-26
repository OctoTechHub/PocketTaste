"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AlertCircle, ArrowRight, Loader2, Plus, Trash2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/api/use-auth";
import {
  useBlendFeed,
  useBlends,
  useCreateBlend,
  useRemoveBlend,
} from "@/hooks/api/use-blend";
import type { BlendFeedItem, BlendMemberSummary } from "@/lib/api/types";
import { LeanMeter, MatchVenn, THEM, YOU, leanColor, ownerColor } from "./seam";

const LABEL = "text-[10px] font-medium uppercase tracking-[0.18em] text-white/45";

function errorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { error?: { message?: string } } } })
    ?.response?.data?.error?.message;
  return detail ?? fallback;
}

// ---------------------------------------------------------------------------

function AddPartner() {
  const [email, setEmail] = useState("");
  const create = useCreateBlend();

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (email.trim()) create.mutate(email.trim());
      }}
      className="rounded-2xl border border-white/10 bg-white/[0.03] p-5"
    >
      <label htmlFor="blend-email" className="block text-sm font-semibold text-white">
        Blend with someone
      </label>
      <p className="mt-1 text-sm text-white/55">
        Enter the email they listen with. You will both get one feed built from both
        histories.
      </p>

      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <input
          id="blend-email"
          type="email"
          inputMode="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="amogh@gmail.com"
          aria-describedby={create.isError ? "blend-email-error" : undefined}
          className="min-h-11 flex-1 rounded-xl border border-white/15 bg-black/40 px-4 text-sm text-white placeholder:text-white/30 focus:border-white/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/60"
        />
        <button
          type="submit"
          disabled={create.isPending || !email.trim()}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-5 text-sm font-semibold text-black transition-opacity hover:opacity-90 disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60"
          style={{ background: `linear-gradient(90deg, ${YOU}, ${THEM})` }}
        >
          {create.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          ) : (
            <Plus className="h-4 w-4" aria-hidden />
          )}
          Start blend
        </button>
      </div>

      {create.isError ? (
        <p
          id="blend-email-error"
          role="alert"
          className="mt-2 flex items-start gap-1.5 text-sm text-red-300"
        >
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          {errorMessage(create.error, "That did not work. Check the address and try again.")}
        </p>
      ) : null}
      {create.isSuccess && create.data?.created === false ? (
        <p role="status" className="mt-2 text-sm text-white/55">
          You already blend with {create.data.members.find((m) => !m.is_you)?.display_name}.
        </p>
      ) : null}
    </form>
  );
}

// ---------------------------------------------------------------------------

function FeedRow({
  item,
  members,
  rank,
}: {
  item: BlendFeedItem;
  members: BlendMemberSummary[];
  rank: number;
}) {
  const [you, them] = members;
  const accent = item.owner === "shared" ? ownerColor("shared", members) : leanColor(item.lean);
  const ownerName =
    item.owner === "shared"
      ? "Both"
      : members.find((member) => member.user_id === item.owner)?.display_name ?? "—";

  return (
    <li
      className="group relative flex gap-4 rounded-2xl border border-white/10 bg-white/[0.02] p-4 transition-colors hover:bg-white/[0.05]"
      style={{ borderLeft: `2px solid ${accent}` }}
    >
      <span className={cn(LABEL, "w-6 pt-1 tabular-nums")}>{String(rank).padStart(2, "0")}</span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <Link
            href={`/watch/${item.content_id}`}
            className="text-base font-semibold text-white hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60"
          >
            {item.title}
          </Link>
          <span
            className="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
            style={{ background: `color-mix(in oklab, ${accent} 22%, transparent)`, color: accent }}
          >
            {ownerName}
          </span>
          <span className="text-[11px] text-white/35">
            {item.genres.slice(0, 2).join(" · ")} · {item.language}
          </span>
        </div>

        <p className="mt-1 line-clamp-2 text-sm text-white/55">{item.description}</p>
        <p className="mt-2 text-[13px] text-white/70">{item.reason}</p>

        <div className="mt-3 max-w-sm">
          <LeanMeter
            lean={item.lean}
            youScore={item.per_member[you.user_id] ?? 0}
            themScore={item.per_member[them.user_id] ?? 0}
            youLabel={you.display_name}
            themLabel={them.display_name}
          />
        </div>
      </div>

      <div className="shrink-0 text-right">
        <p className="text-lg font-bold tabular-nums text-white">{item.score.toFixed(2)}</p>
        <p className={LABEL}>blend</p>
      </div>
    </li>
  );
}

// ---------------------------------------------------------------------------

function BlendDetail({ blendId }: { blendId: string }) {
  const { data, isPending, isError, error, refetch } = useBlendFeed(blendId, 18);

  if (isPending) {
    return (
      <div className="space-y-3" aria-busy="true" aria-live="polite">
        <div className="h-40 animate-pulse rounded-2xl bg-white/[0.04]" />
        {[0, 1, 2, 3].map((index) => (
          <div key={index} className="h-28 animate-pulse rounded-2xl bg-white/[0.03]" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div role="alert" className="rounded-2xl border border-red-500/25 bg-red-500/5 p-5">
        <p className="text-sm text-red-200">
          {errorMessage(error, "The blend could not be built.")}
        </p>
        <button
          type="button"
          onClick={() => refetch()}
          className="mt-3 min-h-11 rounded-xl border border-white/20 px-4 text-sm font-medium text-white hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60"
        >
          Try again
        </button>
      </div>
    );
  }

  const [you, them] = data.members;
  const match = data.taste_match;
  const mix = data.mix;
  const total = data.items.length || 1;
  const share = (count: number) => Math.round((count / total) * 100);

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 sm:p-6">
        <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-center">
          <MatchVenn
            match={match.overall}
            youLabel={you.display_name}
            themLabel={them.display_name}
          />

          <div className="min-w-0 flex-1">
            <h2 className="text-xl font-bold text-white">
              {you.display_name} <span className="text-white/35">and</span> {them.display_name}
            </h2>
            <p className="mt-1 text-sm text-white/55">{match.basis}.</p>

            <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
              {[
                ["Taste vector", match.taste_vector],
                ["Genre", match.genre_overlap],
                ["Language", match.language_overlap],
                ["Shared library", match.shared_library],
              ].map(([label, value]) => (
                <div key={label as string}>
                  <dt className={LABEL}>{label}</dt>
                  <dd className="mt-0.5 text-lg font-bold tabular-nums text-white">
                    {Math.round((value as number) * 100)}%
                  </dd>
                </div>
              ))}
            </dl>

            <p className="mt-3 text-sm text-white/45">
              {match.shared_titles === 0
                ? "No finished title in common yet."
                : `${match.shared_titles} title${match.shared_titles === 1 ? "" : "s"} you have both finished.`}
            </p>
          </div>
        </div>

        {/* Composition of the feed, as a single honest bar. */}
        <div className="mt-6">
          <div className="flex items-baseline justify-between">
            <span className={LABEL}>This feed</span>
            <span className="text-[11px] text-white/45">
              {data.items.length} of {data.candidate_pool_size} candidates
            </span>
          </div>
          <div className="mt-2 flex h-2 overflow-hidden rounded-full bg-white/5">
            <div style={{ width: `${share(mix[you.user_id] ?? 0)}%`, background: YOU }} />
            <div
              style={{
                width: `${share(mix.shared ?? 0)}%`,
                background: `color-mix(in oklab, ${YOU} 50%, ${THEM})`,
              }}
            />
            <div style={{ width: `${share(mix[them.user_id] ?? 0)}%`, background: THEM }} />
          </div>
          <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[11px] text-white/60">
            <Legend color={YOU} label={`${you.display_name} ${mix[you.user_id] ?? 0}`} />
            <Legend
              color={`color-mix(in oklab, ${YOU} 50%, ${THEM})`}
              label={`Shared ${mix.shared ?? 0}`}
            />
            <Legend color={THEM} label={`${them.display_name} ${mix[them.user_id] ?? 0}`} />
          </div>
        </div>
      </section>

      <ol className="space-y-3">
        {data.items.map((item, index) => (
          <FeedRow key={item.content_id} item={item} members={data.members} rank={index + 1} />
        ))}
      </ol>

      <p className="text-[11px] leading-relaxed text-white/35">
        Scored with the same ranker as your own recommendations, once per person, then
        combined as {data.method.aggregation}. {data.method.why_not_average}
      </p>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="h-2 w-2 rounded-full" style={{ background: color }} aria-hidden />
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------

export function BlendShell() {
  const { isAuthenticated } = useAuth();
  const { data, isPending } = useBlends();
  const remove = useRemoveBlend();
  const [activeId, setActiveId] = useState<string | null>(null);

  const blends = useMemo(() => data?.blends ?? [], [data]);

  useEffect(() => {
    if (!activeId && blends.length) setActiveId(blends[0].blend_id);
    if (activeId && !blends.some((blend) => blend.blend_id === activeId)) {
      setActiveId(blends[0]?.blend_id ?? null);
    }
  }, [blends, activeId]);

  if (!isAuthenticated) {
    return (
      <main className="mx-auto max-w-3xl px-4 pb-24 pt-28 sm:px-8">
        <h1 className="text-3xl font-black tracking-tight text-white">Blend</h1>
        <p className="mt-2 text-white/55">Sign in to build a feed with someone else.</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-4 pb-24 pt-28 sm:px-8">
      <header>
        <p className={LABEL}>Two listeners, one feed</p>
        <h1 className="mt-1 text-3xl font-black tracking-tight text-white sm:text-4xl">
          Blend
        </h1>
        <p className="mt-2 max-w-xl text-white/55">
          Add someone by email. Every story below is scored for both of you and labelled
          with whose taste it came from.
        </p>
      </header>

      <div className="mt-8">
        <AddPartner />
      </div>

      {isPending ? (
        <div className="mt-6 h-12 animate-pulse rounded-xl bg-white/[0.04]" aria-busy="true" />
      ) : blends.length === 0 ? (
        <section className="mt-6 rounded-2xl border border-dashed border-white/15 p-8 text-center">
          <p className="text-white">No blends yet.</p>
          <p className="mt-1 text-sm text-white/50">
            Add a listener above and their history joins yours.
          </p>
        </section>
      ) : (
        <>
          {blends.length > 1 ? (
            <div className="mt-6 flex flex-wrap gap-2" role="tablist" aria-label="Your blends">
              {blends.map((blend) => {
                const partner = blend.members.find((member) => !member.is_you);
                const active = blend.blend_id === activeId;
                return (
                  <button
                    key={blend.blend_id}
                    role="tab"
                    aria-selected={active}
                    onClick={() => setActiveId(blend.blend_id)}
                    className={cn(
                      "inline-flex min-h-11 items-center gap-2 rounded-xl border px-4 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60",
                      active
                        ? "border-white/40 bg-white/10 font-semibold text-white"
                        : "border-white/10 text-white/60 hover:bg-white/5",
                    )}
                  >
                    {partner?.display_name ?? "Blend"}
                    <span className="tabular-nums text-white/40">
                      {Math.round(blend.taste_match.overall * 100)}%
                    </span>
                  </button>
                );
              })}
            </div>
          ) : null}

          <div className="mt-6">{activeId ? <BlendDetail blendId={activeId} /> : null}</div>

          {activeId ? (
            <button
              type="button"
              onClick={() => remove.mutate(activeId)}
              disabled={remove.isPending}
              className="mt-8 inline-flex min-h-11 items-center gap-2 rounded-xl border border-white/10 px-4 text-sm text-white/50 transition-colors hover:border-red-500/40 hover:text-red-300 disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60"
            >
              <Trash2 className="h-4 w-4" aria-hidden />
              End this blend
            </button>
          ) : null}
        </>
      )}

      <Link
        href="/"
        className="mt-10 inline-flex items-center gap-1.5 text-sm text-white/45 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60"
      >
        Back to browsing
        <ArrowRight className="h-3.5 w-3.5" aria-hidden />
      </Link>
    </main>
  );
}
