"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

/**
 * Z-stack composition (per spec):
 *   z-0: pure black
 *   z-1: FallingPattern  — density 0.5, duration 300s, opacity 15%
 *   z-2: LampContainer   — cyan conic gradient + heavy blur, top, opacity 60%
 *
 * This is the ambient layer. Page content sits at z-10 above it.
 */
export function AmbientBackground({ className }: { className?: string }) {
  return (
    <div className={cn("pointer-events-none fixed inset-0 overflow-hidden bg-black", className)}>
      <FallingPattern density={0.5} durationSec={300} opacity={0.15} />
      <LampGlow />
    </div>
  );
}

// ---------- Lamp ---------------------------------------------------------------

function LampGlow() {
  return (
    <div className="absolute inset-x-0 top-0 z-[2] flex h-[55vh] items-start justify-center">
      {/* Two soft conic cones meeting at the top-center, blurred into a lamp */}
      <div className="relative h-full w-full">
        <div
          className="absolute left-1/2 top-0 h-[34rem] w-[34rem] -translate-x-1/2 -translate-y-1/3 rounded-full opacity-60 animate-pulse-glow"
          style={{
            background:
              "radial-gradient(circle at center, rgba(34,211,238,0.55), rgba(34,211,238,0.18) 35%, transparent 65%)",
          }}
        />
        <div
          className="absolute left-1/2 top-[8rem] h-[14rem] w-[60rem] -translate-x-1/2 opacity-50"
          style={{
            background:
              "conic-gradient(from 90deg at 50% 100%, transparent 0deg, rgba(34,211,238,0.35) 90deg, rgba(34,211,238,0.35) 270deg, transparent 360deg)",
            filter: "blur(48px)",
            maskImage: "linear-gradient(to bottom, black 30%, transparent 100%)",
          }}
        />
        {/* Thin horizon line where the lamp would meet a surface */}
        <div className="absolute left-1/2 top-[18rem] h-px w-[28rem] -translate-x-1/2 bg-gradient-to-r from-transparent via-glow-line to-transparent" />
      </div>
    </div>
  );
}

// ---------- FallingPattern -----------------------------------------------------

type Particle = {
  left: number;     // 0..100 (vw)
  delay: number;    // s
  size: number;     // px
  duration: number; // s (~ durationSec ± jitter)
  rotate: number;   // deg
};

function FallingPattern({
  density,
  durationSec,
  opacity,
}: {
  density: number;
  durationSec: number;
  opacity: number;
}) {
  // density 0.5 → ~24 particles across the viewport.
  // Generated AFTER mount only — Math.random() would cause an SSR/CSR
  // hydration mismatch if we did it during render.
  const [particles, setParticles] = useState<Particle[]>([]);

  useEffect(() => {
    const count = Math.round(48 * density);
    const arr: Particle[] = [];
    for (let i = 0; i < count; i++) {
      arr.push({
        left: Math.random() * 100,
        delay: -Math.random() * durationSec,
        size: 1 + Math.random() * 2,
        duration: durationSec * (0.7 + Math.random() * 0.6),
        rotate: Math.random() * 360,
      });
    }
    setParticles(arr);
  }, [density, durationSec]);

  return (
    <div className="absolute inset-0 z-[1]" style={{ opacity }}>
      {particles.map((p, i) => (
        <motion.div
          key={i}
          initial={{ y: "-10vh", opacity: 0 }}
          animate={{ y: "110vh", opacity: [0, 0.9, 0.9, 0] }}
          transition={{
            duration: p.duration,
            delay: p.delay,
            repeat: Infinity,
            ease: "linear",
          }}
          className="absolute rounded-full bg-white/40"
          style={{
            left: `${p.left}%`,
            width: p.size,
            height: p.size,
            transform: `rotate(${p.rotate}deg)`,
          }}
        />
      ))}
    </div>
  );
}
