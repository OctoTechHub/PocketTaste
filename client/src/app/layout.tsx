import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Script from "next/script";
import "./globals.css";

import { AppProviders } from "@/components/providers/app-providers";

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
// the light palette on reload.
const themeInit = `try{if(localStorage.getItem('bolsillo.theme')==='dark'){document.documentElement.classList.add('dark');}}catch(e){}`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      // The theme-init script sets the `dark` class on <html> before hydration,
      // so the class deliberately differs from the server render. Tell React not
      // to warn about this one element's attributes.
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <Script id="theme-init" strategy="beforeInteractive">
          {themeInit}
        </Script>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
