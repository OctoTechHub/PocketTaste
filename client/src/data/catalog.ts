// Unified catalog: real videos (Angry Prash) first, then audio stories.
import type { ContentItem, ContentRow } from "./content";
import { storiesRows } from "./stories";
import { videoRows } from "./videos";

export const rows: ContentRow[] = [...videoRows, ...storiesRows];

/** Featured hero — prefer a real video (has a real thumbnail + plays video). */
export const hero: ContentItem = videoRows[0]?.titles[0] ?? storiesRows[0].titles[0];

export const allItems: ContentItem[] = rows.flatMap((row) => row.titles);
