"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AudioLines, Bell, LogOut, Search } from "lucide-react";
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
  const pathname = usePathname();
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
        "fixed inset-x-0 top-0 z-50 border-b transition-colors duration-300",
        // On paper the header can't rely on a dark scrim for separation, so it
        // fades the page colour down over the hero and hardens to a hairline
        // rule once you scroll past it.
        scrolled
          ? "border-border bg-background/85 backdrop-blur-md"
          : "border-transparent bg-gradient-to-b from-background via-background/70 to-transparent",
      )}
    >
      <div className="flex items-center gap-6 px-4 py-3 sm:px-12">
        <Link href="/" className="flex select-none items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-card">
            <AudioLines className="h-5 w-5" strokeWidth={2.75} />
          </span>
          <span className="text-2xl font-black tracking-tight text-foreground">
            Bolsillo
          </span>
        </Link>

        <nav className="hidden items-center gap-5 text-sm text-muted-foreground md:flex">
          {NAV.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "transition-colors hover:text-foreground",
                  // Current section is marked by weight and ink, not colour
                  // alone, so it survives greyscale and CVD.
                  active && "font-semibold text-foreground underline decoration-highlight decoration-2 underline-offset-8",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-4 text-foreground">
          <button
            type="button"
            aria-label="Search"
            onClick={() => setSearchOpen(true)}
            className="flex items-center gap-2 transition-opacity hover:opacity-70"
          >
            <Search className="h-5 w-5" />
            <kbd className="hidden rounded border border-border bg-card px-1.5 py-0.5 text-[10px] text-muted-foreground lg:inline-block">
              ⌘K
            </kbd>
          </button>

          <button type="button" aria-label="Notifications" className="transition-opacity hover:opacity-70">
            <Bell className="h-5 w-5" />
          </button>

          {isAuthenticated ? (
            <div className="flex items-center gap-2">
              <span
                className="flex h-8 w-8 items-center justify-center rounded bg-primary text-sm font-bold text-primary-foreground"
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
