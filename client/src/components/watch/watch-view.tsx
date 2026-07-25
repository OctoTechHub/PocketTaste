"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { Bell, ChevronLeft, Download, Share2, ThumbsDown, ThumbsUp } from "lucide-react";

import type { ContentItem } from "@/data/content";
import { cn } from "@/lib/utils";
import { usePlaybackRef } from "@/hooks/api/use-playback-tracking";
import { TranscriptSection } from "@/components/watch/transcript-section";
import { Button } from "@/components/ui/button";
import { Magnify } from "@/components/magnify";
import { GlowCard, GlowCardGrid } from "@/components/glow-card-grid";
import { SiteHeader } from "@/components/site-header";
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

const EASE = [0.16, 1, 0.3, 1] as const;

const sub = (v: ContentItem) => `${v.channel}${v.views ? ` · ${v.views}` : ""}`;

export function WatchView({
  video,
  recommendations,
}: {
  video: ContentItem;
  recommendations: ContentItem[];
}) {
  const upNext = recommendations.slice(0, 6);
  const more = recommendations.slice(6, 18);

  // Logs play / complete / drop-off for this title to POST /activity.
  const videoRef = usePlaybackRef(video.id);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />

      <main className="mx-auto max-w-7xl px-4 pb-16 pt-20 sm:px-8">
        <Link
          href="/"
          className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ChevronLeft className="h-4 w-4" /> Back to browse
        </Link>

        <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
          {/* Player + details */}
          <div>
            <motion.div
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, ease: EASE }}
            >
              <VideoPlayer className="rounded-xl border border-border">
                <VideoPlayerContent
                  ref={videoRef}
                  slot="media"
                  src={video.audio}
                  poster={video.wideThumb}
                  playsInline
                  preload="metadata"
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
            </motion.div>

            <VideoDetails video={video} />
            <TranscriptSection contentId={video.id} />
          </div>

          {/* Up next */}
          <aside>
            <h2 className="mb-3 text-lg font-bold">Up Next</h2>
            <div className="grid gap-3">
              {upNext.map((v, i) => (
                <GlowCard
                  key={v.id}
                  index={i}
                  thumb={v.thumb}
                  name={v.name}
                  handle={sub(v)}
                  meta={v.duration}
                  href={`/watch/${v.id}`}
                />
              ))}
            </div>
          </aside>
        </div>

        {/* Recommendations with Magnify cursor HUD */}
        <section className="mt-14">
          <motion.h2
            initial={{ opacity: 0, y: 8 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, ease: EASE }}
            className="mb-4 text-xl font-bold"
          >
            Recommended for you
          </motion.h2>

          <Magnify
            color={[0.55, 0.62, 0.98]}
            size={120}
            zoom={1.6}
            haze={0.25}
            className="rounded-2xl"
          >
            <GlowCardGrid className="lg:grid-cols-4">
              {more.map((v, i) => (
                <GlowCard
                  key={v.id}
                  index={i}
                  thumb={v.thumb}
                  name={v.name}
                  handle={sub(v)}
                  meta={v.duration}
                  href={`/watch/${v.id}`}
                />
              ))}
            </GlowCardGrid>
          </Magnify>
        </section>
      </main>
    </div>
  );
}

function VideoDetails({ video }: { video: ContentItem }) {
  const initial = video.channel.charAt(0).toUpperCase();

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={{ show: { transition: { staggerChildren: 0.06, delayChildren: 0.15 } } }}
      className="mt-4"
    >
      <motion.h1
        variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }}
        transition={{ duration: 0.45, ease: EASE }}
        className="text-xl font-bold leading-snug sm:text-2xl"
      >
        {video.name}
      </motion.h1>

      <motion.div
        variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }}
        transition={{ duration: 0.45, ease: EASE }}
        className="mt-3 flex flex-wrap items-center gap-3"
      >
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-chart-1 to-primary text-sm font-bold text-primary-foreground">
            {initial}
          </span>
          <div className="leading-tight">
            <p className="font-semibold">{video.channel}</p>
            <p className="text-xs text-muted-foreground">{video.views || "Recommended"}</p>
          </div>
          <motion.div whileTap={{ scale: 0.94 }} whileHover={{ scale: 1.03 }}>
            <Button className="ml-1 gap-2 rounded-full">
              <Bell className="h-4 w-4" /> Subscribe
            </Button>
          </motion.div>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <div className="flex items-center overflow-hidden rounded-full bg-secondary">
            <ActionButton className="rounded-l-full pl-4 pr-3">
              <ThumbsUp className="h-4 w-4" /> Like
            </ActionButton>
            <span className="h-6 w-px bg-border" />
            <ActionButton className="rounded-r-full px-3">
              <ThumbsDown className="h-4 w-4" />
            </ActionButton>
          </div>
          <ActionButton className="rounded-full bg-secondary px-4">
            <Share2 className="h-4 w-4" /> Share
          </ActionButton>
          <ActionButton className="rounded-full bg-secondary px-4">
            <Download className="h-4 w-4" /> Save
          </ActionButton>
        </div>
      </motion.div>

      <motion.div
        variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }}
        transition={{ duration: 0.45, ease: EASE }}
        className="mt-4 rounded-xl bg-muted p-4 text-sm"
      >
        <p className="font-medium text-foreground">
          {video.views || "Trending"} &nbsp;·&nbsp; Featured on StreamHub
        </p>
        <p className="mt-2 text-muted-foreground">
          Now playing <span className="text-foreground">{video.name}</span> from{" "}
          <span className="text-foreground">{video.channel}</span>. Enjoy the show, then keep the
          binge going with the hand-picked recommendations below.
        </p>
      </motion.div>
    </motion.div>
  );
}

function ActionButton({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.button
      type="button"
      whileTap={{ scale: 0.92 }}
      whileHover={{ y: -1 }}
      className={cn(
        "flex items-center gap-2 py-2 text-sm font-medium text-secondary-foreground transition-colors hover:bg-accent",
        className,
      )}
    >
      {children}
    </motion.button>
  );
}
