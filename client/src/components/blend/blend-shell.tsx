"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AlertCircle, Clock, Loader2, Play, RotateCw, Users, X } from "lucide-react";

import { SiteHeader } from "@/components/site-header";
import { Card, Reveal, SectionTitle, TabHeader } from "@/components/studio/ui";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/api/use-auth";
import {
  useBlendStream,
  useBlends,
  useCreateBlend,
  useRemoveBlend,
} from "@/hooks/api/use-blend";
import type { BlendFeedItem, BlendMemberSummary } from "@/lib/api/types";
import { BlendMark, LeanBar, SHARED_COLOR, THEM, YOU, initials, leanColor } from "./seam";
import { UnderTheHood } from "./under-the-hood";

function apiMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { error?: { message?: string } } } })
    ?.response?.data?.error?.message;
  return detail ?? fallback;
}

function runtime(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  return hours ? `${hours}h ${minutes}m` : `${minutes}m`;
}

// ---------------------------------------------------------------------------
// Invite — the only way a blend comes into existence. Nothing is pre-blended.
// ---------------------------------------------------------------------------

function InviteCard({ compact = false }: { compact?: boolean }) {
  const [email, setEmail] = useState("");
  const create = useCreateBlend();
  const alreadyExisted = create.isSuccess && create.data?.created === false;

  return (
    <Card spotlight={!compact}>
      {compact ? (
        <label htmlFor="blend-email" className="text-sm font-semibold text-foreground">
          Blend with someone else
        </label>
      ) : (
        <>
          <h2 className="text-xl font-bold text-foreground">Put your taste together</h2>
          <p className="mt-1 max-w-md text-sm leading-relaxed text-muted-foreground">
            Enter the email your friend listens with. We rank the whole catalogue for each
            of you, then build one feed neither of you would have found alone.
          </p>
        </>
      )}

      <form
        onSubmit={(event) => {
          event.preventDefault();
          const value = email.trim();
          if (value) create.mutate(value, { onSuccess: () => setEmail("") });
        }}
        className="mt-4 flex flex-col gap-2 sm:flex-row"
      >
        <input
          id="blend-email"
          type="email"
          inputMode="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="friend@gmail.com"
          aria-label="Your friend's email address"
          aria-describedby={create.isError ? "blend-email-error" : undefined}
          className="min-h-11 flex-1 rounded-full border border-white/10 bg-white/[0.04] px-5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <button
          type="submit"
          disabled={create.isPending || !email.trim()}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-full bg-primary px-7 text-sm font-bold text-primary-foreground transition-transform duration-150 hover:scale-[1.02] disabled:pointer-events-none disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring motion-reduce:hover:scale-100"
        >
          {create.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" aria-hidden />
          ) : null}
          {create.isPending ? "Blending" : "Blend"}
        </button>
      </form>

      {/* Reserved so a message never pushes the layout down. */}
      <div className="mt-2 min-h-5" aria-live="polite">
        {create.isError ? (
          <p
            id="blend-email-error"
            role="alert"
            className="flex items-center gap-1.5 text-[13px] text-destructive"
          >
            <AlertCircle className="h-3.5 w-3.5 shrink-0" aria-hidden />
            {apiMessage(create.error, "That did not work. Check the address and try again.")}
          </p>
        ) : alreadyExisted ? (
          <p className="text-[13px] text-muted-foreground">
            You already blend with{" "}
            {create.data?.members.find((member) => !member.is_you)?.display_name}.
          </p>
        ) : null}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------

function Hero({
  members,
  match,
  itemCount,
  poolSize,
  settled,
}: {
  members: BlendMemberSummary[];
  match: number;
  itemCount: number;
  poolSize: number;
  settled: boolean;
}) {
  const [you, them] = members;
  return (
    <div
      className="rounded-2xl border border-white/10 p-5 sm:p-6"
      style={{
        background: `linear-gradient(135deg, color-mix(in oklab, ${YOU} 26%, transparent), color-mix(in oklab, ${THEM} 26%, transparent))`,
      }}
    >
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
        <BlendMark
          match={match}
          youLabel={you.display_name}
          themLabel={them.display_name}
          settled={settled}
        />
        <div className="min-w-0 flex-1">
          <p className="text-xs font-black uppercase tracking-[0.2em] text-primary">Blend</p>
          <h2 className="mt-1 truncate text-2xl font-bold text-foreground sm:text-4xl">
            {you.display_name} <span className="text-muted-foreground">+</span>{" "}
            {them.display_name}
          </h2>
          <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
            <span className="font-semibold text-foreground">
              {Math.round(match * 100)}% taste match
            </span>
            <span aria-hidden>·</span>
            <span>{itemCount} stories</span>
            <span aria-hidden>·</span>
            <span>from {poolSize} candidates</span>
          </p>
        </div>
      </div>
    </div>
  );
}

function TrackRow({
  item,
  members,
  index,
}: {
  item: BlendFeedItem;
  members: BlendMemberSummary[];
  index: number;
}) {
  const [you, them] = members;
  const accent = item.owner === "shared" ? SHARED_COLOR : leanColor(item.lean);
  const ownerName =
    item.owner === "shared"
      ? "Both"
      : members.find((member) => member.user_id === item.owner)?.display_name ?? "—";

  return (
    <li className="group grid grid-cols-[24px_minmax(0,1fr)_auto] items-center gap-3 rounded-xl px-2 py-2.5 transition-colors hover:bg-white/[0.05] sm:grid-cols-[24px_minmax(0,2fr)_minmax(0,1fr)_auto] sm:gap-4 sm:px-3">
      <span className="relative grid h-6 w-6 place-items-center">
        <span className="text-sm tabular-nums text-muted-foreground group-hover:opacity-0">
          {index + 1}
        </span>
        <Play
          className="absolute h-3.5 w-3.5 fill-current text-foreground opacity-0 group-hover:opacity-100"
          aria-hidden
        />
      </span>

      <div className="min-w-0">
        <div className="flex min-w-0 items-center gap-2">
          <span
            className="h-2.5 w-2.5 shrink-0 rounded-full"
            style={{ background: accent }}
            aria-hidden
          />
          <Link
            href={`/watch/${item.content_id}`}
            className="truncate text-sm font-semibold text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {item.title}
          </Link>
        </div>
        <p className="mt-0.5 truncate pl-[18px] text-xs text-muted-foreground">
          {ownerName} · {item.genres.slice(0, 2).join(", ")} · {item.language}
        </p>
      </div>

      {/* Dropped rather than wrapped below the title on small screens. */}
      <p className="hidden min-w-0 truncate text-xs text-muted-foreground sm:block">
        {item.reason}
      </p>

      <div className="flex items-center gap-3 sm:gap-4">
        <div className="hidden lg:block">
          <LeanBar
            lean={item.lean}
            youScore={item.per_member[you.user_id] ?? 0}
            themScore={item.per_member[them.user_id] ?? 0}
            youLabel={you.display_name}
            themLabel={them.display_name}
          />
        </div>
        <span className="flex w-14 shrink-0 items-center justify-end gap-1 text-xs tabular-nums text-muted-foreground">
          <Clock className="h-3 w-3" aria-hidden />
          {runtime(item.duration_seconds)}
        </span>
      </div>
    </li>
  );
}

function MixBar({
  members,
  mix,
  total,
}: {
  members: BlendMemberSummary[];
  mix: Record<string, number>;
  total: number;
}) {
  const [you, them] = members;
  const safe = total || 1;
  const parts = [
    { label: you.display_name, count: mix[you.user_id] ?? 0, color: YOU },
    { label: "Both", count: mix.shared ?? 0, color: SHARED_COLOR },
    { label: them.display_name, count: mix[them.user_id] ?? 0, color: THEM },
  ];
  return (
    <Card spotlight={false}>
      <p className="text-xs font-black uppercase tracking-[0.2em] text-muted-foreground">
        Who this feed came from
      </p>
      <div className="mt-3 flex h-2 gap-0.5 overflow-hidden rounded-full bg-white/5">
        {parts.map((part) => (
          <span
            key={part.label}
            style={{ width: `${(part.count / safe) * 100}%`, background: part.color }}
          />
        ))}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-[13px] text-muted-foreground">
        {parts.map((part) => (
          <li key={part.label} className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ background: part.color }} aria-hidden />
            <span className="text-foreground">{part.label}</span>
            <span className="tabular-nums">{part.count}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function BlendView({ blendId }: { blendId: string }) {
  const { stages, feed, error, isStreaming, restart } = useBlendStream(blendId, 18);
  const remove = useRemoveBlend();

  if (error) {
    return (
      <Card spotlight={false}>
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
        <button
          type="button"
          onClick={() => restart()}
          className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-full bg-primary px-5 text-sm font-bold text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <RotateCw className="h-3.5 w-3.5" aria-hidden />
          Try again
        </button>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {feed ? (
        <Hero
          members={feed.members}
          match={feed.taste_match.overall}
          itemCount={feed.items.length}
          poolSize={feed.candidate_pool_size}
          settled
        />
      ) : (
        // Same height as the settled hero, so the log below never jumps.
        <div className="h-[172px] animate-pulse rounded-2xl border border-white/10 bg-white/[0.03] motion-reduce:animate-none sm:h-[164px]" />
      )}

      <UnderTheHood stages={stages} isStreaming={isStreaming} />

      {feed ? (
        <>
          <MixBar members={feed.members} mix={feed.mix} total={feed.items.length} />

          <Card spotlight={false} className="p-2 sm:p-3">
            <ol>
              {feed.items.map((item, index) => (
                <TrackRow key={item.content_id} item={item} members={feed.members} index={index} />
              ))}
            </ol>
          </Card>

          <p className="px-1 text-xs leading-relaxed text-muted-foreground">
            Ranked with the same engine as your own recommendations, once per person, then
            combined as {feed.method.aggregation}. {feed.method.why_not_average}
          </p>

          <button
            type="button"
            onClick={() => remove.mutate(blendId)}
            disabled={remove.isPending}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-full px-4 text-[13px] font-semibold text-muted-foreground transition-colors hover:text-foreground disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="h-3.5 w-3.5" aria-hidden />
            End this blend
          </button>
        </>
      ) : (
        <div className="space-y-2" aria-hidden>
          {[0, 1, 2, 3, 4, 5].map((row) => (
            <div
              key={row}
              className="h-[52px] animate-pulse rounded-xl border border-white/10 bg-white/[0.03] motion-reduce:animate-none"
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

export function BlendShell() {
  const { isAuthenticated, account } = useAuth();
  const { data, isPending } = useBlends();
  const [activeId, setActiveId] = useState<string | null>(null);

  const blends = useMemo(() => data?.blends ?? [], [data]);

  useEffect(() => {
    if (blends.length === 0) {
      if (activeId !== null) setActiveId(null);
      return;
    }
    if (!activeId || !blends.some((blend) => blend.blend_id === activeId)) {
      setActiveId(blends[0].blend_id);
    }
  }, [blends, activeId]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main className="mx-auto max-w-6xl px-4 pb-20 pt-24 sm:px-8">
        <header className="mb-6">
          <p className="text-xs font-black uppercase tracking-[0.2em] text-primary">Blend</p>
          <h1 className="mt-1 text-2xl font-bold sm:text-3xl">
            {account?.display_name ? `${account.display_name} and a friend` : "Two listeners, one feed"}
          </h1>
        </header>

        {!isAuthenticated ? (
          <Card className="text-center" spotlight={false}>
            <p className="font-semibold text-foreground">Sign in to blend with a friend</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Use “Sign in” in the top-right. A blend reads both listening histories, so it
              needs your account.
            </p>
          </Card>
        ) : isPending ? (
          <div className="h-[220px] animate-pulse rounded-2xl border border-white/10 bg-white/[0.03] motion-reduce:animate-none" />
        ) : blends.length === 0 ? (
          <Reveal>
            <TabHeader
              icon={Users}
              title="Start a blend"
              subtitle="Nothing here until you add someone — blends are never made for you."
            />
            <InviteCard />
          </Reveal>
        ) : (
          <div className="space-y-6">
            {blends.length > 1 ? (
              <nav className="flex flex-wrap gap-2" aria-label="Your blends">
                {blends.map((blend) => {
                  const partner = blend.members.find((member) => !member.is_you);
                  const active = blend.blend_id === activeId;
                  return (
                    <button
                      key={blend.blend_id}
                      type="button"
                      aria-current={active ? "true" : undefined}
                      onClick={() => setActiveId(blend.blend_id)}
                      className={cn(
                        "inline-flex min-h-11 items-center gap-2 rounded-full px-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        active
                          ? "bg-primary text-primary-foreground"
                          : "border border-white/10 text-muted-foreground hover:text-foreground",
                      )}
                    >
                      <span
                        className="grid h-5 w-5 place-items-center rounded-full text-[10px] font-black text-white"
                        style={{ background: THEM }}
                        aria-hidden
                      >
                        {initials(partner?.display_name ?? "?")}
                      </span>
                      {partner?.display_name ?? "Blend"}
                    </button>
                  );
                })}
              </nav>
            ) : null}

            {activeId ? <BlendView key={activeId} blendId={activeId} /> : null}

            <SectionTitle title="Add another" />
            <InviteCard compact />
          </div>
        )}
      </main>
    </div>
  );
}
