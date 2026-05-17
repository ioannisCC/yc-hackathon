"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

/**
 * Z-stack composition:
 *   z-0: deep slate black base
 *   z-1: FallingPattern  — mathematical radial-gradient streaks scrolling vertically
 *   z-2: LampGlow       — two conic gradients meeting at top, masked, bulb + horizon line
 *
 * Mounts as a fixed background. Page content lives at z-10 above it.
 */
export function AmbientBackground({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "pointer-events-none fixed inset-0 overflow-hidden bg-[#020617]",
        className,
      )}
    >
      <FallingPattern />
      <LampGlow />
      {/* Bottom vignette so step cards have somewhere to sit visually */}
      <div className="absolute inset-x-0 bottom-0 z-[3] h-[40vh] bg-gradient-to-t from-[#020617] via-[#020617]/60 to-transparent" />
    </div>
  );
}

/* ---------- LampGlow ---------------------------------------------------------- */
/* Two stacked conic gradients meeting at top-center; each masked to a cone, then
 * blurred. Bulb is a single rounded blur. Horizon line sits where the lamp's
 * physical bar would be. Subtle scale animation on mount for life. */

function LampGlow() {
  return (
    <div className="absolute inset-x-0 top-0 z-[2] flex h-[80vh] items-start justify-center overflow-hidden">
      <div className="relative isolate flex w-full flex-1 scale-y-125 items-center justify-center">
        {/* Left cone */}
        <motion.div
          initial={{ opacity: 0.4, width: "15rem" }}
          animate={{ opacity: 1, width: "30rem" }}
          transition={{ delay: 0.2, duration: 1.0, ease: [0.22, 1, 0.36, 1] }}
          style={{
            backgroundImage:
              "conic-gradient(from 70deg at center top, #22d3ee, transparent, transparent)",
          }}
          className="absolute right-1/2 top-[6rem] h-56 w-[30rem] overflow-visible text-white"
        >
          <div className="absolute bottom-0 left-0 z-20 h-40 w-full bg-[#020617] [mask-image:linear-gradient(to_top,white,transparent)]" />
          <div className="absolute bottom-0 left-0 z-20 h-full w-40 bg-[#020617] [mask-image:linear-gradient(to_right,white,transparent)]" />
        </motion.div>

        {/* Right cone */}
        <motion.div
          initial={{ opacity: 0.4, width: "15rem" }}
          animate={{ opacity: 1, width: "30rem" }}
          transition={{ delay: 0.2, duration: 1.0, ease: [0.22, 1, 0.36, 1] }}
          style={{
            backgroundImage:
              "conic-gradient(from 290deg at center top, transparent, transparent, #22d3ee)",
          }}
          className="absolute left-1/2 top-[6rem] h-56 w-[30rem] text-white"
        >
          <div className="absolute bottom-0 right-0 z-20 h-full w-40 bg-[#020617] [mask-image:linear-gradient(to_left,white,transparent)]" />
          <div className="absolute bottom-0 right-0 z-20 h-40 w-full bg-[#020617] [mask-image:linear-gradient(to_top,white,transparent)]" />
        </motion.div>

        {/* Blur band where the cones end */}
        <div className="absolute top-[18rem] h-48 w-full translate-y-12 scale-x-150 bg-[#020617] blur-2xl" />
        <div className="absolute top-[18rem] z-50 h-48 w-full bg-transparent opacity-10 backdrop-blur-md" />

        {/* Big diffuse bulb */}
        <div className="absolute top-[14rem] z-50 h-36 w-[28rem] -translate-y-1/2 rounded-full bg-cyan-500 opacity-50 blur-3xl" />

        {/* Brighter inner bulb */}
        <motion.div
          initial={{ width: "8rem" }}
          animate={{ width: "16rem" }}
          transition={{ delay: 0.2, duration: 1.0, ease: [0.22, 1, 0.36, 1] }}
          className="absolute top-[8rem] z-30 h-36 w-64 rounded-full bg-cyan-400 blur-2xl"
        />

        {/* Sharp horizon line */}
        <motion.div
          initial={{ width: "15rem", opacity: 0 }}
          animate={{ width: "30rem", opacity: 1 }}
          transition={{ delay: 0.4, duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          className="absolute top-[7rem] z-50 h-px w-[30rem] bg-cyan-400/90 shadow-[0_0_12px_rgba(34,211,238,0.9)]"
        />

        {/* Top cap — hides the gradients above the horizon */}
        <div className="absolute top-0 z-40 h-[7rem] w-full bg-[#020617]" />
      </div>
    </div>
  );
}

/* ---------- FallingPattern --------------------------------------------------- */
/* Reference-grade. 12 horizontal rows of radial-gradient streaks (4px × 100px)
 * plus tiny dots, each row positioned independently, all scrolling downward via
 * background-position animation. A radial-gradient overlay adds dotted grain.
 * Generated client-only to avoid SSR/CSR mismatch. */

const COLOR = "rgba(34, 211, 238, 0.55)";
const BG = "#020617";

const STREAK_ROWS = [
  235, 252, 150, 253, 204, 134, 179, 299, 215, 281, 158, 210,
] as const;

function streakGradients(rows: readonly number[]): string {
  const parts: string[] = [];
  for (const h of rows) {
    parts.push(`radial-gradient(4px 100px at 0px ${h}px, ${COLOR}, transparent)`);
    parts.push(`radial-gradient(4px 100px at 300px ${h}px, ${COLOR}, transparent)`);
    parts.push(`radial-gradient(1.5px 1.5px at 150px ${h / 2}px, ${COLOR} 100%, transparent 150%)`);
  }
  return parts.join(", ");
}

function streakSizes(rows: readonly number[]): string {
  const sizes: string[] = [];
  for (const h of rows) sizes.push(`300px ${h}px`, `300px ${h}px`, `300px ${h}px`);
  return sizes.join(", ");
}

function startPositions(rows: readonly number[]): string {
  const out: string[] = [];
  rows.forEach((h, i) => {
    const x = i * 25;
    out.push(`${x}px ${h - 15}px`, `${x + 3}px ${h - 15}px`, `${150 + x}px ${h / 2 + 70}px`);
  });
  return out.join(", ");
}

function endPositions(rows: readonly number[]): string {
  const out: string[] = [];
  rows.forEach((h, i) => {
    const x = i * 25;
    const y = 5000 + (i * 800) + h;
    out.push(`${x}px ${y}px`, `${x + 3}px ${y}px`, `${150 + x}px ${y / 2}px`);
  });
  return out.join(", ");
}

function FallingPattern() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted) return null;

  const bgImage = streakGradients(STREAK_ROWS);
  const bgSize = streakSizes(STREAK_ROWS);
  const start = startPositions(STREAK_ROWS);
  const end = endPositions(STREAK_ROWS);

  return (
    <div className="absolute inset-0 z-[1] opacity-30">
      <motion.div
        initial={{ backgroundPosition: start }}
        animate={{ backgroundPosition: [start, end] }}
        transition={{
          duration: 300,
          ease: "linear",
          repeat: Infinity,
        }}
        className="absolute inset-0"
        style={{
          backgroundColor: BG,
          backgroundImage: bgImage,
          backgroundSize: bgSize,
        }}
      />
      {/* Dotted grain overlay — gives the streaks texture */}
      <div
        className="absolute inset-0"
        style={{
          backdropFilter: "blur(0.6em)",
          backgroundImage: `radial-gradient(circle at 50% 50%, transparent 0, transparent 2px, ${BG} 2px)`,
          backgroundSize: "8px 8px",
        }}
      />
    </div>
  );
}
