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
  /** Set for stories narrated through the Studio copilot (Sarvam TTS). Lets the
   * home feed show a "Newly Released" shelf without a real media host. */
  hasAudio?: boolean;
};

export type ContentRow = {
  id: string;
  label: string;
  titles: ContentItem[];
};
