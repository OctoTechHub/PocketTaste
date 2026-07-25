import Link from "next/link";
import { Play } from "lucide-react";

import type { ContentItem } from "@/data/content";
import { TiltCard } from "@/components/motion/tilt-card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/** A single content tile: cover art on a beui 3D tilt card. */
export function TitleCard({ title, rank }: { title: ContentItem; rank?: number }) {
  return (
    <Link href={`/watch/${title.id}`} className="relative flex shrink-0 items-center">
      {rank !== undefined && (
        <span
          aria-hidden
          className="select-none text-[7rem] font-black leading-none text-background [-webkit-text-stroke:3px_var(--muted-foreground)]"
        >
          {rank}
        </span>
      )}

      <TiltCard
        max={8}
        className={cn(
          "group/card aspect-video w-[220px] rounded-lg border border-border/60 bg-muted sm:w-[300px]",
          rank !== undefined && "-ml-6",
        )}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={title.thumb}
          alt={title.name}
          loading="lazy"
          className="absolute inset-0 h-full w-full object-cover"
        />

        <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/90 via-black/10 to-transparent" />

        {title.duration && (
          <Badge className="absolute right-2 top-2 border-0 bg-black/70 font-mono text-white tabular-nums">
            {title.duration}
          </Badge>
        )}

        <div className="absolute inset-x-0 bottom-0 p-3">
          <h3 className="line-clamp-2 text-sm font-semibold text-white drop-shadow-sm">
            {title.name}
          </h3>
          <p className="mt-0.5 line-clamp-1 text-xs text-white/70">
            {title.channel}
            {title.views ? ` · ${title.views}` : ""}
          </p>
        </div>

        {/* Hover: play affordance */}
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 backdrop-blur-[1px] transition-opacity duration-200 group-hover/card:opacity-100">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-white text-black shadow-lg">
            <Play className="h-5 w-5 translate-x-px fill-current" />
          </span>
        </div>
      </TiltCard>
    </Link>
  );
}
