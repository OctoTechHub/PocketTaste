"use client";

import Link from "next/link";
import { Info, Play } from "lucide-react";

import type { ContentItem } from "@/data/content";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";
import {
  VideoPlayer,
  VideoPlayerContent,
  VideoPlayerControlBar,
  VideoPlayerMuteButton,
  VideoPlayerPlayButton,
  VideoPlayerSeekBackwardButton,
  VideoPlayerSeekForwardButton,
  VideoPlayerTimeDisplay,
  VideoPlayerTimeRange,
  VideoPlayerVolumeRange,
} from "@/components/kibo-ui/video-player";

export function Billboard({ hero }: { hero: ContentItem }) {
  return (
    <section className="relative h-[62vh] min-h-[440px] w-full sm:h-[82vh]">
      {/* Full-bleed kibo-ui player */}
      <VideoPlayer className="absolute inset-0 h-full w-full rounded-none border-0">
        <VideoPlayerContent
          slot="media"
          src={hero.audio}
          poster={hero.wideThumb}
          autoPlay
          muted
          loop
          playsInline
          preload="auto"
          crossOrigin=""
        />
        <VideoPlayerControlBar>
          <VideoPlayerPlayButton />
          <VideoPlayerSeekBackwardButton />
          <VideoPlayerSeekForwardButton />
          <VideoPlayerTimeRange />
          <VideoPlayerTimeDisplay showDuration />
          <VideoPlayerMuteButton />
          <VideoPlayerVolumeRange />
        </VideoPlayerControlBar>
      </VideoPlayer>

      {/* Legibility overlays (never block the controls) */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-background via-background/40 to-transparent" />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-background to-transparent" />

      {/* Copy + CTAs */}
      <div className="pointer-events-none absolute inset-x-0 bottom-24 px-4 sm:bottom-28 sm:px-12">
        <div className="max-w-xl">
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.3em] text-primary sm:text-sm">
            Featured Today
          </p>
          <h1 className="line-clamp-3 text-3xl font-black text-white drop-shadow-lg sm:text-5xl">
            {hero.name}
          </h1>
          <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-white/80">
            <span className="font-semibold text-primary">{hero.channel}</span>
            {hero.views && <span>{hero.views}</span>}
            {hero.duration && (
              <span className="rounded border border-white/40 px-1.5 font-mono">{hero.duration}</span>
            )}
          </div>
          <div className="pointer-events-auto mt-5 flex flex-wrap gap-3">
            <Link
              href={`/watch/${hero.id}`}
              className={cn(
                buttonVariants({ size: "lg" }),
                "h-11 gap-2 px-6 text-base bg-white text-black hover:bg-white/85",
              )}
            >
              <Play className="h-5 w-5 fill-current" /> Play
            </Link>
            <Link
              href={`/watch/${hero.id}`}
              className={cn(
                buttonVariants({ variant: "secondary", size: "lg" }),
                "h-11 gap-2 px-6 text-base bg-white/20 text-white backdrop-blur hover:bg-white/30",
              )}
            >
              <Info className="h-5 w-5" /> More Info
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
