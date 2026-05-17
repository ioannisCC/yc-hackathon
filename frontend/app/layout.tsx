import "./globals.css";
import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import type { ReactNode } from "react";

import { AmbientBackground } from "@/components/ambient-background";
import { GlassFilter } from "@/components/glass-filter";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "AI Receptionist — answer every call",
  description:
    "Paste any business URL. In under five minutes, your business has a phone number staffed by a voice AI that books real appointments.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#020617",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-[#020617] font-sans text-neutral-50 antialiased">
        {/* Singleton SVG filter for all liquid-glass surfaces */}
        <GlassFilter />
        <AmbientBackground />
        <div className="relative z-10">{children}</div>
      </body>
    </html>
  );
}
