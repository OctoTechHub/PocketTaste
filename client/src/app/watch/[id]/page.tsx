import { notFound } from "next/navigation";

import { getRecommendations, getVideo } from "@/data/queries";
import { WatchView } from "@/components/watch/watch-view";

export default async function WatchPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const video = getVideo(id);
  if (!video) notFound();

  const recommendations = getRecommendations(id);
  return <WatchView video={video} recommendations={recommendations} />;
}
