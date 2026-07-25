"use client";

import { Fragment } from "react";

import { Billboard } from "@/components/billboard";
import { ChannelMarquee } from "@/components/channel-marquee";
import { ContentRow } from "@/components/content-row";
import { ForYouRow } from "@/components/for-you-row";
import { Loader } from "@/components/motion/loader";
import { useCatalogRows } from "@/hooks/api/use-catalog";

/** The home feed, entirely from GET /catalog — hero + genre shelves. */
export function CatalogHome() {
  const { data, isLoading, isError, error } = useCatalogRows();

  if (isLoading) {
    return (
      <div className="flex min-h-[70vh] flex-col items-center justify-center gap-4 text-muted-foreground">
        <Loader variant="bars" size={40} />
        <p className="text-sm">Loading the catalog…</p>
      </div>
    );
  }

  if (isError || !data || !data.hero) {
    return (
      <div className="flex min-h-[70vh] flex-col items-center justify-center gap-3 px-6 text-center">
        <p className="text-lg font-semibold text-foreground">
          Couldn’t load the catalog
        </p>
        <p className="max-w-md text-sm text-muted-foreground">
          {error instanceof Error
            ? error.message
            : "Is the API server running on http://127.0.0.1:8000?"}
        </p>
      </div>
    );
  }

  const { rows, hero } = data;
  const collections = rows.map((row) => row.label);

  return (
    <>
      <Billboard hero={hero} />

      {/* Rows overlap the hero's lower gradient, Netflix-style */}
      <div className="relative z-10 -mt-16 sm:-mt-24">
        {/* Personalised rail — visible once signed in */}
        <ForYouRow />

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
