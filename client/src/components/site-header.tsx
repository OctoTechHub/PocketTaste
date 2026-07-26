"use client";

import Link from "next/link";
import { Bell, LogOut, Search } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";
import { useScrolled } from "@/hooks/use-scrolled";
import { useAuth } from "@/hooks/api/use-auth";
import { AuthDrawer } from "@/components/auth/auth-drawer";
import { SearchCommand } from "@/components/search/search-command";

const NAV: { label: string; href: string }[] = [
  { label: "Home", href: "/" },
  { label: "Blend", href: "/blend" },
  { label: "Creator Studio", href: "/studio" },
  { label: "Admin", href: "/admin" },
];

export function SiteHeader() {
  const scrolled = useScrolled();
  const { account, isAuthenticated, logout } = useAuth();
  const [searchOpen, setSearchOpen] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);

  const initial =
    account?.display_name?.trim()?.[0]?.toUpperCase() ??
    account?.email?.[0]?.toUpperCase() ??
    "";

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
            <Link
              key={item.href}
              href={item.href}
              className={cn("transition-colors hover:text-white", i === 0 && "font-semibold text-white")}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-4 text-white">
          <button
            type="button"
            aria-label="Search"
            onClick={() => setSearchOpen(true)}
            className="flex items-center gap-2 transition-opacity hover:opacity-70"
          >
            <Search className="h-5 w-5" />
            <kbd className="hidden rounded border border-white/30 px-1.5 py-0.5 text-[10px] text-white/60 lg:inline-block">
              ⌘K
            </kbd>
          </button>

          <button type="button" aria-label="Notifications" className="transition-opacity hover:opacity-70">
            <Bell className="h-5 w-5" />
          </button>

          {isAuthenticated ? (
            <div className="flex items-center gap-2">
              <span
                className="flex h-8 w-8 items-center justify-center rounded bg-gradient-to-br from-chart-4 to-primary text-sm font-bold text-white"
                title={account?.email}
              >
                {initial}
              </span>
              <button
                type="button"
                aria-label="Sign out"
                onClick={logout}
                className="transition-opacity hover:opacity-70"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setAuthOpen(true)}
              className="rounded-full bg-primary px-4 py-1.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
            >
              Sign in
            </button>
          )}
        </div>
      </div>

      <SearchCommand open={searchOpen} onOpenChange={setSearchOpen} />
      <AuthDrawer open={authOpen} onOpenChange={setAuthOpen} />
    </header>
  );
}
