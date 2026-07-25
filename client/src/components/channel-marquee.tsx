import { Marquee } from "@/components/motion/marquee";

/** Infinite pause-on-hover strip of pills (beui Marquee). */
export function ChannelMarquee({
  items,
  label = "Popular channels",
}: {
  items: string[];
  label?: string;
}) {
  return (
    <section className="py-4">
      <p className="mb-3 px-4 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground sm:px-12">
        {label}
      </p>
      <Marquee pauseOnHover speed={38} gap="0.75rem" className="py-1">
        {items.map((item) => (
          <span
            key={item}
            className="whitespace-nowrap rounded-full border border-border bg-card px-4 py-2 text-sm font-medium text-card-foreground"
          >
            {item}
          </span>
        ))}
      </Marquee>
    </section>
  );
}
