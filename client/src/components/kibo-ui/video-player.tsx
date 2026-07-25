"use client";

// kibo-ui video player — thin, themeable wrappers over media-chrome.
// API mirrors https://www.kibo-ui.com/components/video-player
import {
  MediaControlBar,
  MediaController,
  MediaMuteButton,
  MediaPlayButton,
  MediaSeekBackwardButton,
  MediaSeekForwardButton,
  MediaTimeDisplay,
  MediaTimeRange,
  MediaVolumeRange,
} from "media-chrome/react";
import type { ComponentProps, CSSProperties } from "react";

import { cn } from "@/lib/utils";

export type VideoPlayerProps = ComponentProps<typeof MediaController>;

export const VideoPlayer = ({ style, className, ...props }: VideoPlayerProps) => {
  const theme = {
    "--media-primary-color": "#ffffff",
    "--media-secondary-color": "transparent",
    "--media-text-color": "#ffffff",
    "--media-control-hover-background": "rgba(255,255,255,0.16)",
    "--media-range-bar-color": "#e50914",
    "--media-range-thumb-background": "#e50914",
    "--media-range-track-height": "4px",
    "--media-font-family": "var(--font-sans, system-ui, sans-serif)",
    ...style,
  } as CSSProperties;

  return (
    <MediaController
      className={cn("aspect-video w-full overflow-hidden bg-black", className)}
      style={theme}
      {...props}
    />
  );
};

export type VideoPlayerContentProps = ComponentProps<"video">;

export const VideoPlayerContent = ({ className, ...props }: VideoPlayerContentProps) => (
  // media-chrome mutates the <video> (adds tabindex) after mount → suppress the
  // resulting, benign hydration diff.
  // eslint-disable-next-line jsx-a11y/media-has-caption
  <video
    suppressHydrationWarning
    className={cn("h-full w-full object-cover", className)}
    {...props}
  />
);

export type VideoPlayerControlBarProps = ComponentProps<typeof MediaControlBar>;
export const VideoPlayerControlBar = (props: VideoPlayerControlBarProps) => (
  <MediaControlBar {...props} />
);

export type VideoPlayerTimeRangeProps = ComponentProps<typeof MediaTimeRange>;
export const VideoPlayerTimeRange = ({ className, ...props }: VideoPlayerTimeRangeProps) => (
  <MediaTimeRange className={cn("flex-1", className)} {...props} />
);

export type VideoPlayerTimeDisplayProps = ComponentProps<typeof MediaTimeDisplay>;
export const VideoPlayerTimeDisplay = (props: VideoPlayerTimeDisplayProps) => (
  <MediaTimeDisplay {...props} />
);

export type VideoPlayerVolumeRangeProps = ComponentProps<typeof MediaVolumeRange>;
export const VideoPlayerVolumeRange = (props: VideoPlayerVolumeRangeProps) => (
  <MediaVolumeRange {...props} />
);

export type VideoPlayerPlayButtonProps = ComponentProps<typeof MediaPlayButton>;
export const VideoPlayerPlayButton = (props: VideoPlayerPlayButtonProps) => (
  <MediaPlayButton {...props} />
);

export type VideoPlayerSeekBackwardButtonProps = ComponentProps<typeof MediaSeekBackwardButton>;
export const VideoPlayerSeekBackwardButton = (props: VideoPlayerSeekBackwardButtonProps) => (
  <MediaSeekBackwardButton {...props} />
);

export type VideoPlayerSeekForwardButtonProps = ComponentProps<typeof MediaSeekForwardButton>;
export const VideoPlayerSeekForwardButton = (props: VideoPlayerSeekForwardButtonProps) => (
  <MediaSeekForwardButton {...props} />
);

export type VideoPlayerMuteButtonProps = ComponentProps<typeof MediaMuteButton>;
export const VideoPlayerMuteButton = (props: VideoPlayerMuteButtonProps) => (
  <MediaMuteButton {...props} />
);
