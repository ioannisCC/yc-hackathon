/* eslint-disable */
// REFERENCE ONLY — do not import. See _references/README.md.
//
// Visual DNA: refractive liquid-glass surface.
// - backdrop-blur to refract the layer behind
// - inner top-edge highlight (white/12) and bottom-edge shadow (black/40)
// - color-mix tinted base so the glass tints with the ambient
// - subtle inset ring on focus

import { motion } from "framer-motion";

export function LiquidGlassButton({
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <motion.button
      whileTap={{ scale: 0.97 }}
      whileHover={{ scale: 1.02 }}
      className="relative overflow-hidden rounded-full px-6 py-3
                 bg-[color-mix(in_oklab,white_8%,transparent)]
                 backdrop-blur-xl border border-white/10
                 shadow-[inset_0_1px_0_rgba(255,255,255,0.18),inset_0_-1px_0_rgba(0,0,0,0.4),0_8px_30px_rgba(0,0,0,0.45)]
                 transition-colors hover:border-white/20"
      {...(props as object)}
    >
      <span className="relative z-10 font-medium tracking-wide">{children}</span>
      {/* refractive highlight */}
      <span aria-hidden className="pointer-events-none absolute inset-x-2 top-px h-px bg-gradient-to-r from-transparent via-white/40 to-transparent" />
    </motion.button>
  );
}
