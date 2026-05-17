"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export type IslandMode = "collapsed" | "expanded" | "status";

const HEIGHT: Record<IslandMode, number> = {
  collapsed: 48,
  status: 52,
  expanded: 64,
};

const MIN_WIDTH: Record<IslandMode, { mobile: number; desktop: number }> = {
  collapsed: { mobile: 240, desktop: 280 },
  status:    { mobile: 280, desktop: 360 },
  expanded:  { mobile: 320, desktop: 620 },
};

/** Apple-style Dynamic Island. Morphs shape via framer layout + width spring;
 *  children cross-fade keyed on mode. Responsive: caps at viewport - 32px on
 *  small screens; tightens vertical rhythm. */
export function DynamicIsland({
  mode,
  children,
  className,
}: {
  mode: IslandMode;
  children: ReactNode;
  className?: string;
}) {
  // Match the desktop minimum on >=640px, mobile minimum below.
  const [isDesktop, setIsDesktop] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 640px)");
    const update = () => setIsDesktop(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  const minWidth = isDesktop ? MIN_WIDTH[mode].desktop : MIN_WIDTH[mode].mobile;

  return (
    <motion.div
      layout
      transition={{ type: "spring", stiffness: 260, damping: 30, mass: 0.85 }}
      style={{
        minWidth,
        height: HEIGHT[mode],
        maxWidth: "calc(100vw - 32px)",
      }}
      className={cn(
        "relative isolate mx-auto flex items-center justify-center overflow-hidden rounded-full",
        // Glass surface — flatter and darker than the buttons so the island reads
        // as the singular "anchor" element of the page.
        "bg-black/55 backdrop-blur-2xl",
        "shadow-[inset_0_1px_0_rgba(255,255,255,0.10),inset_0_-1px_0_rgba(0,0,0,0.55),inset_0_0_0_1px_rgba(255,255,255,0.07),0_20px_60px_rgba(0,0,0,0.6),0_0_40px_rgba(34,211,238,0.10)]",
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
          className="flex h-full w-full items-center justify-center px-4 sm:px-5"
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
}

/* ---------- Cycling placeholder ---------------------------------------------- */

const CYCLE = [
  "paste any business URL",
  "build an AI receptionist",
  "go live in 5 minutes",
  "your agent answers calls",
];

/** Renders one phrase at a time, fading letter-by-letter; advances every 4s. */
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
        "text-[13px] sm:text-sm font-normal tracking-wide text-white/65",
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
