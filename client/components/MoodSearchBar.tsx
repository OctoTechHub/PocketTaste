"use client";

import { useState } from "react";

const EXAMPLES = [
  "dark office romance, Hindi, 15-min episodes, no horror",
  "something that feels like a rainy Sunday after heartbreak",
  "fast-paced English sci-fi thriller",
  "wholesome small-town love story, slow burn",
];

/** Mood-first / conversational search input with example prompts. */
export function MoodSearchBar({
  onSearch,
  loading,
  active,
  onClear,
}: {
  onSearch: (q: string) => void;
  loading: boolean;
  active: boolean;
  onClear: () => void;
}) {
  const [value, setValue] = useState("");

  const submit = (q: string) => {
    setValue(q);
    onSearch(q);
  };

  return (
    <div className="rounded-2xl border border-border bg-surface/70 p-4 backdrop-blur">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSearch(value);
        }}
        className="flex items-center gap-2"
      >
        <span className="pl-1 text-lg">🔮</span>
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Describe the vibe you want…  e.g. 'dark office romance, Hindi, no horror'"
          className="flex-1 bg-transparent py-1.5 text-sm text-foreground placeholder:text-muted/70 focus:outline-none"
        />
        {active && (
          <button
            type="button"
            onClick={() => {
              setValue("");
              onClear();
            }}
            className="rounded-lg px-2 py-1 text-xs text-muted hover:text-foreground"
          >
            Clear
          </button>
        )}
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-accent px-4 py-1.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
        >
          {loading ? "Thinking…" : "Discover"}
        </button>
      </form>
      <div className="mt-3 flex flex-wrap gap-2">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            onClick={() => submit(ex)}
            className="rounded-full border border-border bg-surface-2/50 px-3 py-1 text-xs text-muted transition hover:border-accent hover:text-foreground"
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
}
