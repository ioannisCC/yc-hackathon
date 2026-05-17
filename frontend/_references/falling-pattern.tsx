/* eslint-disable */
// REFERENCE ONLY — do not import. See _references/README.md.
//
// Visual DNA: ambient falling particles, very low density, very slow,
// very low opacity. Texture, not foreground noise.

import { motion } from "framer-motion";
import { useMemo } from "react";

export function FallingPattern({
  density = 0.5,
  duration = 300,
  className = "opacity-15",
}: {
  density?: number;
  duration?: number;
  className?: string;
}) {
  const particles = useMemo(() => {
    const count = Math.round(48 * density);
    return Array.from({ length: count }, () => ({
      left: Math.random() * 100,
      delay: -Math.random() * duration,
      size: 1 + Math.random() * 2,
      dur: duration * (0.7 + Math.random() * 0.6),
    }));
  }, [density, duration]);

  return (
    <div className={`absolute inset-0 ${className}`}>
      {particles.map((p, i) => (
        <motion.div
          key={i}
          initial={{ y: "-10vh", opacity: 0 }}
          animate={{ y: "110vh", opacity: [0, 0.9, 0.9, 0] }}
          transition={{ duration: p.dur, delay: p.delay, repeat: Infinity, ease: "linear" }}
          className="absolute rounded-full bg-white/40"
          style={{ left: `${p.left}%`, width: p.size, height: p.size }}
        />
      ))}
    </div>
  );
}
