"use client";

import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Tone = "neutral" | "active" | "muted";

const TONE: Record<Tone, { bg: string; border: string; text: string; dot: string }> = {
  neutral: {
    bg: "bg-white/[0.06]",
    border: "border-white/12",
    text: "text-white/85",
    dot: "bg-white/40",
  },
  active: {
    bg: "bg-cyan-400/[0.10]",
    border: "border-cyan-300/40",
    text: "text-cyan-100",
    dot: "bg-cyan-300 shadow-[0_0_10px_rgba(34,211,238,0.9)]",
  },
  muted: {
    bg: "bg-white/[0.03]",
    border: "border-white/8",
    text: "text-white/45",
    dot: "bg-white/25",
  },
};

export function GlassPill({
  tone = "neutral",
  pulse = false,
  children,
  className,
}: {
  tone?: Tone;
  pulse?: boolean;
  children: ReactNode;
  className?: string;
}) {
  const t = TONE[tone];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium tracking-wide backdrop-blur-md",
        t.bg, t.border, t.text,
        className,
      )}
    >
      <motion.span
        aria-hidden
        animate={pulse ? { opacity: [0.6, 1, 0.6] } : { opacity: 1 }}
        transition={pulse ? { duration: 1.6, repeat: Infinity, ease: "easeInOut" } : undefined}
        className={cn("h-1.5 w-1.5 shrink-0 rounded-full", t.dot)}
      />
      {children}
    </span>
  );
}
