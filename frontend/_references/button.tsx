/* eslint-disable */
// REFERENCE ONLY — do not import. See _references/README.md.
//
// Two button flavors that share the liquid-glass DNA:
//   - LiquidButton: cyan-tinted glass with a soft glow underneath. Primary CTA.
//   - MetalButton:  cooler, less saturated, more "industrial". Secondary.
// Spring on press, no spring on hover.

import { motion } from "framer-motion";

export function LiquidButton({ children, ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <motion.button
      whileTap={{ scale: 0.96 }}
      transition={{ type: "spring", stiffness: 400, damping: 18 }}
      className="group relative rounded-full px-6 py-3 font-medium
                 bg-[color-mix(in_oklab,#22d3ee_22%,black_78%)]
                 border border-cyan-300/30
                 shadow-[inset_0_1px_0_rgba(255,255,255,0.25),0_0_24px_rgba(34,211,238,0.35),0_10px_30px_rgba(0,0,0,0.5)]
                 hover:border-cyan-300/50 hover:bg-[color-mix(in_oklab,#22d3ee_28%,black_72%)]
                 transition-colors"
      {...(rest as object)}
    >
      <span className="relative z-10 text-white">{children}</span>
      <span aria-hidden className="pointer-events-none absolute inset-x-3 top-px h-px bg-gradient-to-r from-transparent via-white/50 to-transparent" />
    </motion.button>
  );
}

export function MetalButton({ children, ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <motion.button
      whileTap={{ scale: 0.97 }}
      transition={{ type: "spring", stiffness: 400, damping: 18 }}
      className="rounded-full px-5 py-2.5 text-sm font-medium
                 bg-white/5 border border-white/10
                 shadow-[inset_0_1px_0_rgba(255,255,255,0.1),0_4px_16px_rgba(0,0,0,0.3)]
                 hover:bg-white/10 hover:border-white/20 transition-colors"
      {...(rest as object)}
    >
      {children}
    </motion.button>
  );
}
