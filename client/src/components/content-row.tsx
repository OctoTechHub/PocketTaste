"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import type { ContentRow as ContentRowType } from "@/data/content";
import { useRowScroll } from "@/hooks/use-row-scroll";
import { TitleCard } from "@/components/title-card";

/** A titled, horizontally-scrolling shelf of content tiles. */
export function ContentRow({ row, ranked = false }: { row: ContentRowType; ranked?: boolean }) {
  const { ref, scrollByPage } = useRowScroll();

  return (
    <section className="group/row relative py-3">
      <h2 className="mb-2 px-4 text-lg font-bold text-foreground sm:px-12 md:text-xl">
        {row.label}
      </h2>

      <div className="relative">
        <ArrowButton side="left" onClick={() => scrollByPage("left")} />

        <div
          ref={ref}
          className="no-scrollbar flex gap-2 overflow-x-auto scroll-smooth px-4 pb-6 pt-1 sm:px-12"
        >
          {row.titles.map((title, i) => (
            <TitleCard key={title.id} title={title} rank={ranked ? i + 1 : undefined} />
          ))}
        </div>

        <ArrowButton side="right" onClick={() => scrollByPage("right")} />
      </div>
    </section>
  );
}

function ArrowButton({ side, onClick }: { side: "left" | "right"; onClick: () => void }) {
  const Icon = side === "left" ? ChevronLeft : ChevronRight;
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Scroll ${side}`}
      className={`absolute ${side === "left" ? "left-0" : "right-0"} top-0 bottom-6 z-30 hidden w-12 items-center justify-center bg-background/70 text-foreground opacity-0 transition-opacity duration-200 hover:bg-background/90 group-hover/row:opacity-100 md:flex`}
    >
      <Icon className="h-8 w-8" />
    </button>
  );
}
