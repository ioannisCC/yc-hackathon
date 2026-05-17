"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export type IslandMode = "collapsed" | "expanded" | "status";

const MIN_WIDTH: Record<IslandMode, number> = {
  collapsed: 260,
  status: 340,
  expanded: 620,
};

/** Apple-style Dynamic Island. Morphs shape via framer layout + state-keyed
 *  child cross-fade. */
export function DynamicIsland({
  mode,
  children,
  className,
}: {
  mode: IslandMode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      layout
      transition={{ type: "spring", stiffness: 280, damping: 30, mass: 0.9 }}
      style={{ minWidth: MIN_WIDTH[mode] }}
      className={cn(
        "relative mx-auto flex items-center justify-center",
        "rounded-full px-5 py-2.5",
        "bg-black/70 backdrop-blur-2xl border border-white/10",
        "shadow-[inset_0_1px_0_rgba(255,255,255,0.10),inset_0_-1px_0_rgba(0,0,0,0.6),0_20px_60px_rgba(0,0,0,0.6)]",
        className,
      )}
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={mode}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
          className="flex w-full items-center justify-center"
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
}

/* ---------- letter-by-letter cycling placeholder ----------------------------- */

const CYCLE = [
  "paste any business URL",
  "build an AI receptionist",
  "go live in 5 minutes",
  "your agent answers calls",
];

/** Renders one phrase at a time, fading letter-by-letter, advancing every
 *  4 seconds. Stagger 50ms. */
export function CyclingPlaceholder({ className }: { className?: string }) {
  const [i, setI] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setI((n) => (n + 1) % CYCLE.length), 4000);
    return () => clearInterval(t);
  }, []);

  const phrase = CYCLE[i] ?? CYCLE[0]!;

  return (
    <div
      className={cn(
        "pointer-events-none flex h-6 items-center justify-center overflow-hidden",
        "text-sm font-normal tracking-wide text-white/60",
        className,
      )}
    >
      <AnimatePresence mode="wait">
        <motion.span
          key={phrase}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="flex"
        >
          {phrase.split("").map((ch, idx) => (
            <motion.span
              key={`${phrase}-${idx}`}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{
                duration: 0.4,
                delay: idx * 0.05,
                ease: [0.22, 1, 0.36, 1],
              }}
              className="whitespace-pre"
            >
              {ch}
            </motion.span>
          ))}
        </motion.span>
      </AnimatePresence>
    </div>
  );
}
