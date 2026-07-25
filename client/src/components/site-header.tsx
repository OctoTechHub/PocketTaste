"use client";

import Link from "next/link";
import { Bell, Search } from "lucide-react";

import { cn } from "@/lib/utils";
import { useScrolled } from "@/hooks/use-scrolled";

const NAV = ["Home", "Series", "Films", "New & Popular", "My List"];

export function SiteHeader() {
  const scrolled = useScrolled();

  return (
    <header
      className={cn(
        "fixed inset-x-0 top-0 z-50 transition-colors duration-300",
        scrolled ? "bg-background/95 backdrop-blur" : "bg-gradient-to-b from-black/80 to-transparent",
      )}
    >
      <div className="flex items-center gap-6 px-4 py-3 sm:px-12">
        <Link
          href="/"
          className="select-none text-2xl font-black uppercase tracking-tight text-primary"
        >
          StreamHub
        </Link>

        <nav className="hidden items-center gap-5 text-sm text-white/80 md:flex">
          {NAV.map((item, i) => (
            <a
              key={item}
              href="#"
              className={cn("transition-colors hover:text-white", i === 0 && "font-semibold text-white")}
            >
              {item}
            </a>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-4 text-white">
          <button type="button" aria-label="Search" className="transition-opacity hover:opacity-70">
            <Search className="h-5 w-5" />
          </button>
          <button type="button" aria-label="Notifications" className="transition-opacity hover:opacity-70">
            <Bell className="h-5 w-5" />
          </button>
          <span className="h-8 w-8 rounded bg-gradient-to-br from-chart-4 to-primary" aria-hidden />
        </div>
      </div>
    </header>
  );
}
