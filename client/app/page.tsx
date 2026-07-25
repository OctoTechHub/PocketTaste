"use client";

import { useState } from "react";
import type { RankedSeries } from "@/lib/types";
import { UserProvider, useUser } from "@/features/user/UserProvider";
import { useFeed } from "@/features/feed/useFeed";
import { useProfile } from "@/features/profile/useProfile";
import { useDiscovery } from "@/features/discovery/useDiscovery";
import { Header } from "@/components/Header";
import { MoodSearchBar } from "@/components/MoodSearchBar";
import { Rail } from "@/components/Rail";
import { DiscoveryResults } from "@/components/DiscoveryResults";
import { TasteProfilePanel } from "@/components/TasteProfilePanel";
import { SeriesModal } from "@/components/SeriesModal";

export default function Page() {
  return (
    <UserProvider>
      <HomeScreen />
    </UserProvider>
  );
}

function HomeScreen() {
  const { currentUserId, loading: userLoading, error: userError } = useUser();
  const [refresh, setRefresh] = useState(0);
  const [active, setActive] = useState<RankedSeries | null>(null);

  const bump = () => setRefresh((n) => n + 1);
  const feed = useFeed(currentUserId, refresh);
  const profile = useProfile(currentUserId, refresh);
  const discovery = useDiscovery(currentUserId);

  return (
    <div className="flex min-h-full flex-col">
      <Header />

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-6">
        <MoodSearchBar
          onSearch={discovery.run}
          loading={discovery.loading}
          active={discovery.active}
          onClear={discovery.clear}
        />

        {userError && (
          <p className="mt-6 rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-300">
            Can&apos;t reach the API ({userError}). Is the server running on{" "}
            <code>:4000</code> and seeded?
          </p>
        )}

        <div className="mt-6 grid gap-8 lg:grid-cols-[1fr_320px]">
          <div className="space-y-10">
            {discovery.active ? (
              <DiscoveryResults
                query={discovery.query}
                intent={discovery.intent}
                results={discovery.results}
                loading={discovery.loading}
                error={discovery.error}
                onOpen={setActive}
              />
            ) : (
              <>
                {(userLoading || feed.loading) && (
                  <p className="text-sm text-muted">Loading your feed…</p>
                )}
                {feed.error && <p className="text-sm text-red-400">{feed.error}</p>}
                {feed.data?.map((rail) => (
                  <Rail key={rail.key} rail={rail} onOpen={setActive} />
                ))}
              </>
            )}
          </div>

          <div className="lg:sticky lg:top-20 lg:self-start">
            <TasteProfilePanel profile={profile.data} />
            <p className="mt-4 px-1 text-[11px] leading-relaxed text-muted">
              Open any title to see its transparent ranking breakdown and{" "}
              <span className="text-foreground">simulate listening</span> — the feed re-ranks
              in real time as new behavior comes in.
            </p>
          </div>
        </div>
      </main>

      {active && (
        <SeriesModal
          ranked={active}
          userId={currentUserId}
          onClose={() => setActive(null)}
          onOpen={setActive}
          onLogged={bump}
        />
      )}
    </div>
  );
}
