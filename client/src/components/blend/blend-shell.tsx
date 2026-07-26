"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { AlertCircle, Clock, Loader2, Play, RotateCw, Users, X } from "lucide-react";

import { SiteHeader } from "@/components/site-header";
import { Card, Reveal, SectionTitle } from "@/components/studio/ui";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/api/use-auth";
import {
  useBlendStream,
  useBlends,
  useCreateBlend,
  useRemoveBlend,
} from "@/hooks/api/use-blend";
import type {
  BlendFeed,
  BlendFeedItem,
  BlendMemberSummary,
  BlendSummary,
  TasteMatch,
} from "@/lib/api/types";
import { Helix } from "./helix";
import {
  BasePair,
  LeanBar,
  SHARED_COLOR,
  StrandEnd,
  THEM,
  YOU,
  initials,
  leanColor,
} from "./seam";
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

/** The two-hue wash used behind every blend surface — ember on the left, indigo on
 *  the right, so the page itself reads as a gradient between two people. */
const SEAM_WASH = {
  background: `radial-gradient(120% 150% at 0% 50%, color-mix(in oklab, ${YOU} 14%, transparent), transparent 58%),
               radial-gradient(120% 150% at 100% 50%, color-mix(in oklab, ${THEM} 14%, transparent), transparent 58%)`,
} as const;

// ---------------------------------------------------------------------------
// Invite — the only way a blend comes into existence. Nothing is pre-blended.
// ---------------------------------------------------------------------------

function InviteCard({ compact = false }: { compact?: boolean }) {
  const [email, setEmail] = useState("");
  const create = useCreateBlend();
  const alreadyExisted = create.isSuccess && create.data?.created === false;

  return (
    <div className="relative overflow-hidden rounded-2xl border border-border bg-card">
      {!compact ? (
        <>
          <div aria-hidden className="absolute inset-0" style={SEAM_WASH} />
          {/* Two loose strands, waiting to pair. The invite state *is* the
              unbonded state, so it uses the same picture rather than a stock one. */}
          <div aria-hidden className="absolute inset-x-0 bottom-0 opacity-45">
            <Helix bonded={false} match={0.35} height={96} />
          </div>
        </>
      ) : null}

      <div className={cn("relative", compact ? "p-5" : "px-5 pb-28 pt-6 sm:px-7 sm:pt-7")}>
        {compact ? (
          <label htmlFor="blend-email" className="text-sm font-semibold text-foreground">
            Blend with someone else
          </label>
        ) : (
          <>
            <h2 className="text-xl font-bold text-foreground sm:text-2xl">
              Put your taste together
            </h2>
            <p className="mt-1.5 max-w-md text-sm leading-relaxed text-muted-foreground">
              Enter the email your friend listens with. We rank the whole catalogue for
              each of you, then build one feed neither of you would have found alone.
            </p>
          </>
        )}

        <form
          onSubmit={(event) => {
            event.preventDefault();
            const value = email.trim();
            if (value) create.mutate(value, { onSuccess: () => setEmail("") });
          }}
          className={cn("mt-4 flex flex-col gap-2 sm:flex-row", !compact && "max-w-md")}
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
            className="min-h-11 flex-1 rounded-full border border-border bg-card px-5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <button
            type="submit"
            disabled={create.isPending || !email.trim()}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-full bg-primary px-7 text-sm font-bold text-primary-foreground transition-transform duration-150 hover:scale-[1.02] disabled:pointer-events-none disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring motion-reduce:hover:scale-100"
          >
            {create.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" aria-hidden />
            ) : null}
            {create.isPending ? "Pairing" : "Blend"}
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
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Hero
// ---------------------------------------------------------------------------

/**
 * The four independent views the match is built from.
 *
 * A single 63% invites the question "63% of what?", and the server already
 * answers it — `taste_match` ships its own components and the weighting it used.
 * Showing them turns the headline number from an assertion into something a
 * listener can audit.
 */
function MatchBreakdown({ match }: { match: TasteMatch }) {
  const parts = [
    { label: "Taste vector", value: match.taste_vector, weight: 50 },
    { label: "Genres", value: match.genre_overlap, weight: 25 },
    { label: "Language", value: match.language_overlap, weight: 15 },
    { label: "Shared library", value: match.shared_library, weight: 10 },
  ];
  return (
    <dl className="grid grid-cols-2 gap-x-8 gap-y-5 sm:grid-cols-4">
      {parts.map((part) => (
        <div key={part.label}>
          <dt className="flex items-baseline gap-1.5">
            <span className="truncate text-[11px] text-muted-foreground">{part.label}</span>
            {/* The weight was previously sr-only, which hid the one fact that makes
                the headline number auditable: these four do not count equally. */}
            <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground/55">
              ×{part.weight}%
            </span>
          </dt>
          <dd className="mt-1">
            <span className="text-xl font-bold leading-none tabular-nums tracking-tight text-foreground">
              {Math.round(part.value * 100)}
            </span>
            <span className="ml-px text-[11px] font-medium text-muted-foreground/70">%</span>
            <span className="mt-2 block h-[3px] w-full overflow-hidden rounded-full bg-muted">
              <span
                className="block h-full rounded-full transition-[width] duration-700 ease-out motion-reduce:transition-none"
                style={{
                  width: `${Math.max(2, Math.min(1, part.value) * 100)}%`,
                  // Opacity tracks the weight, so the strand that moves the number
                  // most is also the one that reads loudest.
                  background: SHARED_COLOR,
                  opacity: 0.45 + (part.weight / 50) * 0.55,
                }}
              />
            </span>
          </dd>
        </div>
      ))}
    </dl>
  );
}

function Hero({
  members,
  match,
  feed,
  settled,
}: {
  members: BlendMemberSummary[];
  match: TasteMatch;
  feed: BlendFeed | null;
  settled: boolean;
}) {
  const [you, them] = members;
  const percent = Math.round(match.overall * 100);

  return (
    <section className="relative overflow-hidden rounded-3xl border border-border bg-card shadow-card">
      <div aria-hidden className="absolute inset-0" style={SEAM_WASH} />

      <div className="relative px-4 pb-7 pt-6 sm:px-8 sm:pb-9 sm:pt-8">
        {/* The two people sit at the ends of the molecule. */}
        <div className="flex items-start justify-between gap-4">
          <StrandEnd
            name={you.display_name}
            colour={YOU}
            meta={`${you.events_observed} plays logged`}
          />
          <StrandEnd
            name={them.display_name}
            colour={THEM}
            meta={`${them.events_observed} plays logged`}
            align="right"
          />
        </div>

        {/* ...and the helix is what joins them. It pairs up the moment the
            server's last frame lands, so the animation is the result arriving.
            Given real height here: it is the one picture on the page worth
            watching, and at 124px it read as a divider rather than a subject. */}
        <div className="relative mt-2 sm:mt-3">
          <Helix bonded={settled} match={match.overall} height={184} />

          <div className="pointer-events-none absolute inset-0 grid place-items-center">
            {/* A soft scrim rather than a bordered card: the number needs contrast
                against the coil, but a second card edge inside a card muddies the
                composition and reads as a tooltip pinned over the art. */}
            <div
              aria-hidden
              className="absolute h-[132px] w-[132px] rounded-full sm:h-[150px] sm:w-[150px]"
              style={{
                background: `radial-gradient(closest-side,
                  color-mix(in oklab, var(--card) 88%, transparent) 45%,
                  color-mix(in oklab, var(--card) 0%, transparent) 100%)`,
              }}
            />
            <div
              className={cn(
                "relative text-center transition-all duration-700 ease-out motion-reduce:transition-none",
                settled ? "scale-100 opacity-100" : "scale-95 opacity-60",
              )}
            >
              <p className="flex items-start justify-center font-black leading-[0.85] tracking-[-0.045em] text-foreground">
                <span className="text-[3.75rem] tabular-nums sm:text-[4.75rem]">
                  {settled ? percent : "··"}
                </span>
                {settled ? (
                  <span className="mt-1 text-xl font-bold text-muted-foreground/70 sm:mt-1.5 sm:text-2xl">
                    %
                  </span>
                ) : null}
              </p>
              <p className="mt-2 text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                {settled ? "taste match" : "pairing"}
              </p>
            </div>
          </div>
        </div>

        {feed ? (
          <dl className="mt-3 flex flex-wrap items-baseline justify-center gap-x-7 gap-y-1.5 sm:gap-x-10">
            {[
              { value: feed.items.length, label: "stories" },
              { value: feed.candidate_pool_size, label: "candidates ranked" },
              { value: match.shared_titles, label: "finished by both" },
            ].map((stat) => (
              <div key={stat.label} className="flex items-baseline gap-1.5">
                <dt className="sr-only">{stat.label}</dt>
                <dd className="text-base font-bold tabular-nums text-foreground">{stat.value}</dd>
                <span aria-hidden className="text-[13px] text-muted-foreground">
                  {stat.label}
                </span>
              </div>
            ))}
          </dl>
        ) : (
          <p className="mt-3 text-center text-sm text-muted-foreground">
            Ranking the catalogue for each of you…
          </p>
        )}

        <div className="mt-6 border-t border-border/70 pt-5">
          <MatchBreakdown match={match} />
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Feed
// ---------------------------------------------------------------------------

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
  const shared = item.owner === "shared";
  const ownerName = shared
    ? "Both of you"
    : (members.find((member) => member.user_id === item.owner)?.display_name ?? "—");

  return (
    <li className="group grid grid-cols-[20px_3px_minmax(0,1fr)_auto] items-center gap-2.5 rounded-xl px-2 py-2.5 transition-colors hover:bg-muted sm:grid-cols-[20px_3px_minmax(0,2fr)_minmax(0,1fr)_auto] sm:gap-3.5 sm:px-3">
      <span className="relative grid h-5 w-5 place-items-center">
        <span className="text-[13px] tabular-nums text-muted-foreground group-hover:opacity-0">
          {index + 1}
        </span>
        <Play
          className="absolute h-3.5 w-3.5 fill-current text-foreground opacity-0 group-hover:opacity-100"
          aria-hidden
        />
      </span>

      <BasePair lean={item.lean} shared={shared} />

      <div className="min-w-0">
        <Link
          href={`/watch/${item.content_id}`}
          className="block truncate text-sm font-semibold text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {item.title}
        </Link>
        <p className="mt-0.5 flex items-center gap-1.5 truncate text-xs text-muted-foreground">
          <span
            className="font-medium"
            style={{ color: shared ? SHARED_COLOR : leanColor(item.lean) }}
          >
            {ownerName}
          </span>
          <span aria-hidden>·</span>
          <span className="truncate">{item.genres.slice(0, 2).join(", ")}</span>
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

/** Where the feed came from, as one strand split three ways. */
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
    <div className="border-b border-border/70 px-4 py-4 sm:px-5 sm:py-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="text-[11px] font-black uppercase tracking-[0.2em] text-muted-foreground">
          Who this feed came from
        </p>
        <p className="text-[11px] text-muted-foreground/80">
          fairness pass keeps either of you above a third
        </p>
      </div>

      {/* One rail, split three ways — the same left-to-right you/shared/them
          ordering as the helix above, so the eye reads it without a legend. */}
      <div className="mt-3 flex h-2 gap-1 overflow-hidden">
        {parts.map((part) => (
          <span
            key={part.label}
            className="rounded-full transition-[width] duration-700 ease-out motion-reduce:transition-none"
            style={{ width: `${(part.count / safe) * 100}%`, background: part.color }}
          />
        ))}
      </div>

      <ul className="mt-3 flex flex-wrap items-baseline gap-x-6 gap-y-1.5">
        {parts.map((part) => (
          <li key={part.label} className="flex min-w-0 items-baseline gap-1.5">
            <span
              className="h-2 w-2 shrink-0 translate-y-px rounded-full"
              style={{ background: part.color }}
              aria-hidden
            />
            <span className="text-sm font-bold tabular-nums text-foreground">{part.count}</span>
            <span className="truncate text-[11px] text-muted-foreground">{part.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function BlendView({ summary }: { summary: BlendSummary }) {
  const { stages, feed, error, isStreaming, restart } = useBlendStream(summary.blend_id, 18);
  const remove = useRemoveBlend();

  // Names and the match are already known from the list call, so the hero can be
  // whole from the first frame — only the counts and the pairing wait on the
  // stream. A skeleton here would hide the one animation worth watching.
  const members = feed?.members ?? summary.members;
  const match = feed?.taste_match ?? summary.taste_match;

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
      <Hero members={members} match={match} feed={feed} settled={Boolean(feed)} />

      <UnderTheHood stages={stages} isStreaming={isStreaming} />

      {feed ? (
        <>
          {/* Provenance and the feed are one object: where the rows came from is a
              property of the list, not a separate finding that deserves its own slab. */}
          <Card spotlight={false} className="overflow-hidden p-0">
            <MixBar members={feed.members} mix={feed.mix} total={feed.items.length} />

            <ol className="p-2 sm:p-3">
              {feed.items.map((item, index) => (
                <TrackRow key={item.content_id} item={item} members={feed.members} index={index} />
              ))}
            </ol>
          </Card>

          <div className="flex flex-wrap items-center justify-between gap-3 px-1">
            <p className="max-w-2xl text-xs leading-relaxed text-muted-foreground">
              Ranked with the same engine as your own recommendations, once per person,
              then combined as {feed.method.aggregation}. {feed.method.why_not_average}
            </p>
            <button
              type="button"
              onClick={() => remove.mutate(summary.blend_id)}
              disabled={remove.isPending}
              className="inline-flex min-h-11 shrink-0 items-center gap-1.5 rounded-full px-4 text-[13px] font-semibold text-muted-foreground transition-colors hover:text-foreground disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <X className="h-3.5 w-3.5" aria-hidden />
              End this blend
            </button>
          </div>
        </>
      ) : (
        <div className="space-y-1.5" aria-hidden>
          {[0, 1, 2, 3, 4, 5].map((row) => (
            <div
              key={row}
              className="h-[52px] animate-pulse rounded-xl border border-border bg-card motion-reduce:animate-none"
              style={{ animationDelay: `${row * 90}ms` }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

export function BlendShell() {
  const { isAuthenticated } = useAuth();
  const { data, isPending } = useBlends();
  const [activeId, setActiveId] = useState<string | null>(null);

  const blends = useMemo(() => data?.blends ?? [], [data]);

  // Derived, not synced. `activeId` holds only an explicit choice; the first blend
  // is the fallback whenever that choice is absent or has since been deleted. An
  // effect mirroring the list into state would re-render twice and go stale between
  // the two, for a value that is a one-line lookup.
  const active = blends.find((blend) => blend.blend_id === activeId) ?? blends[0] ?? null;

  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main className="mx-auto max-w-6xl px-4 pb-20 pt-24 sm:px-8">
        {/* The one masthead on the page. The hero used to repeat a "Blend" eyebrow
            directly under this, which read as two titles fighting for the same slot. */}
        <header className="mb-6 sm:mb-8">
          <p className="mb-3 w-fit text-[11px] font-semibold uppercase tracking-[0.3em] marker-sweep">
            Blend
          </p>
          <h1 className="max-w-2xl text-3xl font-bold tracking-[-0.02em] sm:text-4xl">
            Two listeners, one feed
          </h1>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
            Every story below is scored for both of you, then paired — never averaged.
          </p>
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
          <div className="h-[320px] animate-pulse rounded-3xl border border-border bg-card motion-reduce:animate-none" />
        ) : blends.length === 0 ? (
          <Reveal>
            <div className="mb-5 flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                <Users className="h-5 w-5" />
              </span>
              <div>
                <p className="text-lg font-bold text-foreground">Start a blend</p>
                <p className="text-sm text-muted-foreground">
                  Nothing here until you add someone — blends are never made for you.
                </p>
              </div>
            </div>
            <InviteCard />
          </Reveal>
        ) : (
          <div className="space-y-6">
            {blends.length > 1 ? (
              <nav className="flex flex-wrap gap-2" aria-label="Your blends">
                {blends.map((blend) => {
                  const partner = blend.members.find((member) => !member.is_you);
                  const isActive = blend.blend_id === activeId;
                  return (
                    <button
                      key={blend.blend_id}
                      type="button"
                      aria-current={isActive ? "true" : undefined}
                      onClick={() => setActiveId(blend.blend_id)}
                      className={cn(
                        "inline-flex min-h-11 items-center gap-2 rounded-full px-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        isActive
                          ? "bg-primary text-primary-foreground"
                          : "border border-border text-muted-foreground hover:text-foreground",
                      )}
                    >
                      <span
                        className="grid h-5 w-5 place-items-center rounded-full text-[10px] font-black text-white"
                        /* white on THEM measures 5.6:1 */
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

            {active ? <BlendView key={active.blend_id} summary={active} /> : null}

            <SectionTitle title="Add another" />
            <InviteCard compact />
          </div>
        )}
      </main>
    </div>
  );
}
