"use client";

import { Fragment } from "react";
import { WifiOff } from "lucide-react";

import { Billboard } from "@/components/billboard";
import { ChannelMarquee } from "@/components/channel-marquee";
import { ContentRow } from "@/components/content-row";
import { ForYouRow } from "@/components/for-you-row";
import { NewReleasesRow } from "@/components/new-releases-row";
import { Loader } from "@/components/motion/loader";
import { useCatalogRows } from "@/hooks/api/use-catalog";
import { hero as sampleHero, rows as sampleRows } from "@/data/catalog";

/** The home feed, entirely from GET /catalog — hero + genre shelves. */
export function CatalogHome() {
  const { data, isLoading, isError } = useCatalogRows();

  if (isLoading) {
    return (
      <div className="flex min-h-[70vh] flex-col items-center justify-center gap-4 text-muted-foreground">
        <Loader variant="bars" size={40} />
        <p className="text-sm">Loading the catalog…</p>
      </div>
    );
  }

  // A dead API used to leave the home page as a bare error string. It now falls
  // back to the catalog bundled with the client so the app is still walkable —
  // but says so plainly, because sample shelves must never be mistaken for the
  // live catalog.
  const offline = isError || !data || !data.hero;
  const { rows, hero } = offline
    ? { rows: sampleRows, hero: sampleHero }
    : { rows: data.rows, hero: data.hero! };

  const collections = rows.map((row) => row.label);

  return (
    <>
      {offline ? (
        <div
          role="status"
          className="fixed inset-x-0 top-14 z-40 mx-auto flex w-fit max-w-[92vw] items-center gap-2.5 rounded-full border border-border bg-card px-4 py-2 text-sm shadow-lift"
        >
          <WifiOff aria-hidden className="h-4 w-4 shrink-0 text-primary" />
          <span className="text-foreground">
            Showing the bundled sample catalog — the API isn’t reachable.
          </span>
        </div>
      ) : null}

      <Billboard hero={hero} />

      {/* Rows overlap the hero's lower gradient, Netflix-style */}
      <div className="relative z-10 -mt-16 sm:-mt-24">
        {/* Personalised rail — visible once signed in */}
        <ForYouRow />
        {/* Stories published from the Studio copilot (Sarvam-narrated) */}
        <NewReleasesRow />

        {rows.map((row, i) => (
          <Fragment key={row.id}>
            <ContentRow row={row} ranked={i === 0} />
            {i === 1 && (
              <ChannelMarquee label="Browse genres" items={collections} />
            )}
          </Fragment>
        ))}
      </div>
    </>
  );
}
