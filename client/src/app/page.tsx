import { Fragment } from "react";

import { Billboard } from "@/components/billboard";
import { ChannelMarquee } from "@/components/channel-marquee";
import { ContentRow } from "@/components/content-row";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { hero, rows } from "@/data/catalog";

export default function Home() {
  const collections = rows.map((row) => row.label);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />

      <main>
        <Billboard hero={hero} />

        {/* Rows overlap the hero's lower gradient, Netflix-style */}
        <div className="relative z-10 -mt-16 sm:-mt-24">
          {rows.map((row, i) => (
            <Fragment key={row.id}>
              <ContentRow row={row} ranked={i === 0} />
              {i === 1 && <ChannelMarquee label="Browse collections" items={collections} />}
            </Fragment>
          ))}
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
