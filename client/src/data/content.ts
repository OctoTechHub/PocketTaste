// Shared content shape used across the UI, independent of the data source.
export type ContentItem = {
  id: string;
  name: string;
  channel: string;
  duration: string;
  views: string;
  /** Cover/thumbnail image (URL or data URI). */
  thumb: string;
  wideThumb: string;
  /** Link or resource URL. */
  url: string;
  /** Playable media source (audio/video). */
  audio?: string;
};

export type ContentRow = {
  id: string;
  label: string;
  titles: ContentItem[];
};
