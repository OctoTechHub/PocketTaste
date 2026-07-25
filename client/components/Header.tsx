"use client";

import { useUser } from "@/features/user/UserProvider";

/** App header: brand, listener switcher, and the AI-mode indicator. */
export function Header() {
  const { users, currentUserId, setCurrentUserId, health } = useUser();

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-6 py-3">
        <div className="flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-accent to-accent-2 text-sm font-black text-white">
            P
          </span>
          <div className="leading-tight">
            <p className="text-sm font-bold text-foreground">PocketTaste</p>
            <p className="text-[10px] text-muted">AI discovery for long-form audio</p>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-3">
          {health && (
            <span
              className="hidden items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-[11px] text-muted sm:inline-flex"
              title="Which AI backend is powering embeddings + discovery"
            >
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: health.mode === "openai" ? "#34d399" : "#f0a500" }}
              />
              {health.mode === "openai" ? "OpenAI" : "Local fallback"} · {health.catalogSize} series
            </span>
          )}
          <label className="flex items-center gap-2 text-xs text-muted">
            <span className="hidden sm:inline">Browsing as</span>
            <select
              value={currentUserId ?? ""}
              onChange={(e) => setCurrentUserId(e.target.value)}
              className="max-w-[220px] rounded-lg border border-border bg-surface px-2 py-1.5 text-xs text-foreground focus:outline-none"
            >
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.displayName}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
    </header>
  );
}
