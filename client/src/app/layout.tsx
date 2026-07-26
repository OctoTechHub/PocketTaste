import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

import { InlineScript } from "@/components/inline-script";
import { AppProviders } from "@/components/providers/app-providers";
import { THEME_KEY } from "@/lib/theme";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Bolsillo — Audio Stories in Your Pocket",
  description: "Bolsillo — a creator-intelligence audio-stories app.",
};

export const viewport: Viewport = {
  colorScheme: "light dark",
};

// Applies the saved theme before first paint, so switching to dark never flashes
// the light palette on reload. Runs in <head>, ahead of any body content.
const themeInit = `try{if(localStorage.getItem(${JSON.stringify(THEME_KEY)})==='dark'){document.documentElement.classList.add('dark');}}catch(e){}`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // The script adds `dark` to this element's class list before hydration, so
    // React must accept the DOM's className over the one it rendered.
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <InlineScript html={themeInit} />
      </head>
      <body className="min-h-full flex flex-col">
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
