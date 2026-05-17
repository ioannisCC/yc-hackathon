"use client";

import { motion } from "framer-motion";
import { Phone } from "lucide-react";
import { GlassPill } from "@/components/dashboard/glass-pill";
import { formatPhone } from "@/lib/utils";

export function BusinessHeader({
  name,
  phoneNumber,
  isLive,
}: {
  name: string;
  phoneNumber: string;
  isLive: boolean;
}) {
  return (
    <motion.header
      layout
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="flex w-full items-center justify-between gap-3 rounded-2xl border border-white/8 bg-white/[0.025] px-4 py-3 backdrop-blur-xl shadow-[inset_0_1px_0_rgba(255,255,255,0.07),0_8px_28px_rgba(0,0,0,0.4)] sm:px-5 sm:py-3.5"
    >
      <div className="flex min-w-0 items-center gap-3 sm:gap-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-cyan-300/30 bg-cyan-400/[0.08] sm:h-10 sm:w-10">
          <Phone className="h-4 w-4 text-cyan-200" />
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold tracking-tight text-white sm:text-base">
            {name}
          </p>
          <p className="font-mono text-[11px] text-white/55 sm:text-xs">
            {formatPhone(phoneNumber)}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        {isLive ? (
          <GlassPill tone="active" pulse>
            Active call
          </GlassPill>
        ) : (
          <GlassPill tone="muted">Idle</GlassPill>
        )}
        <span className="hidden font-mono text-[10px] uppercase tracking-[0.22em] text-white/35 sm:inline">
          AgentPhone
        </span>
      </div>
    </motion.header>
  );
}
