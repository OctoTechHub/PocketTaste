"use client";

import { useRouter } from "next/navigation";
import { Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { CommandPalette, type CommandItem } from "@/components/motion/command-palette";
import { Loader } from "@/components/motion/loader";
import { useSearch } from "@/hooks/api/use-discovery";

/**
 * Natural-language catalog search over POST /discovery/search, presented in the
 * beui command palette. The query is debounced and fired as a mutation; hits
 * become selectable rows that route to the watch page.
 */
export function SearchCommand({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const search = useSearch();
  const [query, setQuery] = useState("");

  // Debounce the server call so we don't fire on every keystroke.
  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      search.reset();
      return;
    }
    const id = setTimeout(() => {
      search.mutate({ query: q, top_k: 8, answer: false });
    }, 300);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  // Reset transient state whenever the palette closes.
  useEffect(() => {
    if (!open) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setQuery("");
      search.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const items = useMemo<CommandItem[]>(() => {
    const hits = search.data?.hits ?? [];
    return hits.map((hit) => ({
      id: hit.content_id,
      label: hit.title,
      group: hit.genres[0] ? `Genre · ${hit.genres[0]}` : "Results",
      hint: hit.language?.toUpperCase(),
      keywords: hit.genres,
      onSelect: () => {
        onOpenChange(false);
        router.push(`/watch/${hit.content_id}`);
      },
    }));
  }, [search.data, router, onOpenChange]);

  const header =
    query.trim().length >= 2 ? (
      <div className="flex items-center gap-2 border-b border-border px-4 py-2 text-xs text-muted-foreground">
        {search.isPending ? (
          <>
            <Loader variant="dots" size={16} />
            <span>Searching the catalog…</span>
          </>
        ) : search.isError ? (
          <span className="text-destructive">
            Search failed — is the API server running?
          </span>
        ) : (
          <>
            <Sparkles className="h-3.5 w-3.5" />
            <span>
              {items.length} result{items.length === 1 ? "" : "s"} for “{query.trim()}”
            </span>
          </>
        )}
      </div>
    ) : null;

  const empty =
    query.trim().length < 2
      ? "Type at least 2 characters to search stories…"
      : search.isPending
        ? "Searching…"
        : "No stories matched. Try different words.";

  return (
    <CommandPalette
      open={open}
      onOpenChange={onOpenChange}
      query={query}
      onQueryChange={setQuery}
      items={items}
      placeholder="Search stories by theme, plot or vibe…"
      emptyMessage={empty}
      header={header}
    />
  );
}
