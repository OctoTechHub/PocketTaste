import { WatchScreen } from "@/components/watch/watch-screen";

export default async function WatchPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <WatchScreen id={id} />;
}
