/* eslint-disable */
// REFERENCE ONLY — do not import. See _references/README.md.
//
// Visual DNA: Apple Dynamic Island.
// - Glass-morphic black pill anchored at top
// - Smooth shape morph between three states via framer-motion layout
// - Children inside fade-cross between states with AnimatePresence

import { AnimatePresence, motion } from "framer-motion";

type Mode = "collapsed" | "expanded" | "status";

export function DynamicIslandTOC({ mode, children }: { mode: Mode; children: React.ReactNode }) {
  return (
    <motion.div
      layout
      transition={{ type: "spring", stiffness: 280, damping: 30 }}
      className="relative mx-auto flex items-center justify-center rounded-full
                 bg-black/70 backdrop-blur-2xl border border-white/10
                 shadow-[inset_0_1px_0_rgba(255,255,255,0.08),0_20px_60px_rgba(0,0,0,0.6)]
                 px-5 py-2.5 text-sm text-white/90"
      style={{ minWidth: mode === "collapsed" ? 220 : mode === "status" ? 320 : 560 }}
    >
      <AnimatePresence mode="wait">
        <motion.div
          key={mode}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.25 }}
          className="flex w-full items-center justify-center"
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
}
