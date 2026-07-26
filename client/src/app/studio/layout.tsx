"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import type { ReactNode } from "react";

import { SiteHeader } from "@/components/site-header";
import { useAuth } from "@/hooks/api/use-auth";
import { STUDIO_TABS } from "@/components/studio/tabs";
import { Card } from "@/components/studio/ui";

/** Shared chrome for every Studio section: header, auth gate and the tab nav.
 *  Each tab is now its own route under /studio/*. */
export default function StudioLayout({ children }: { children: ReactNode }) {
  const { isAuthenticated, account } = useAuth();
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main className="mx-auto max-w-6xl px-4 pb-20 pt-24 sm:px-8">
        <header className="mb-6">
          <p className="text-xs font-black uppercase tracking-[0.2em] text-primary">
            Creator Studio
          </p>
          <h1 className="mt-1 text-2xl font-bold sm:text-3xl">
            {account?.display_name ? `Welcome, ${account.display_name}` : "Your studio"}
          </h1>
        </header>

        {!isAuthenticated ? (
          <Card className="text-center" spotlight={false}>
            <p className="font-semibold text-foreground">Sign in to open your studio</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Use “Sign in” in the top-right. Opportunities, performance and uploads are tied
              to your creator account.
            </p>
          </Card>
        ) : (
          <>
            <nav className="mb-6 flex flex-wrap gap-2">
              {STUDIO_TABS.map(({ slug, href, label, icon: Icon }) => {
                const active = pathname === href || pathname.startsWith(`${href}/`);
                return (
                  <Link
                    key={slug}
                    href={href}
                    className={`relative inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                      active
                        ? "text-primary-foreground"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {active ? (
                      <motion.span
                        layoutId="studio-tab-pill"
                        className="absolute inset-0 -z-10 rounded-full bg-primary"
                        transition={{ type: "spring", stiffness: 480, damping: 38 }}
                      />
                    ) : (
                      <span className="absolute inset-0 -z-10 rounded-full border border-border" />
                    )}
                    <Icon className="h-4 w-4" />
                    {label}
                  </Link>
                );
              })}
            </nav>

            {children}
          </>
        )}
      </main>
    </div>
  );
}
