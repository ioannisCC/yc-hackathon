/* eslint-disable */
// REFERENCE ONLY — do not import. See _references/README.md.
//
// Mathematical falling pattern — 12 radial-gradient row systems scrolled
// vertically via background-position animation. Generates an ambient texture
// that reads as motion without being foreground noise.
"use client";

import type React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

type FallingPatternProps = React.ComponentProps<"div"> & {
  color?: string;
  backgroundColor?: string;
  duration?: number;
  blurIntensity?: string;
  density?: number;
};

export function FallingPattern({
  color = "var(--primary)",
  backgroundColor = "var(--background)",
  duration = 150,
  blurIntensity = "1em",
  density = 1,
  className,
}: FallingPatternProps) {
  const rows = [235, 252, 150, 253, 204, 134, 179, 299, 215, 281, 158, 210];
  const bgImage = rows
    .flatMap((h) => [
      `radial-gradient(4px 100px at 0px ${h}px, ${color}, transparent)`,
      `radial-gradient(4px 100px at 300px ${h}px, ${color}, transparent)`,
      `radial-gradient(1.5px 1.5px at 150px ${h / 2}px, ${color} 100%, transparent 150%)`,
    ])
    .join(", ");
  const bgSize = rows.flatMap((h) => [`300px ${h}px`, `300px ${h}px`, `300px ${h}px`]).join(", ");

  const start = rows.flatMap((h, i) => {
    const x = i * 25;
    return [`${x}px ${h - 15}px`, `${x + 3}px ${h - 15}px`, `${150 + x}px ${h / 2 + 70}px`];
  }).join(", ");

  const end = rows.flatMap((h, i) => {
    const x = i * 25;
    const y = 5000 + i * 800 + h;
    return [`${x}px ${y}px`, `${x + 3}px ${y}px`, `${150 + x}px ${y / 2}px`];
  }).join(", ");

  return (
    <div className={cn("relative h-full w-full p-1", className)}>
      <motion.div
        initial={{ backgroundPosition: start }}
        animate={{ backgroundPosition: [start, end] }}
        transition={{ duration, ease: "linear", repeat: Infinity }}
        className="absolute inset-0"
        style={{ backgroundColor, backgroundImage: bgImage, backgroundSize: bgSize }}
      />
      <div
        className="absolute inset-0"
        style={{
          backdropFilter: `blur(${blurIntensity})`,
          backgroundImage: `radial-gradient(circle at 50% 50%, transparent 0, transparent 2px, ${backgroundColor} 2px)`,
          backgroundSize: `${8 * density}px ${8 * density}px`,
        }}
      />
    </div>
  );
}
