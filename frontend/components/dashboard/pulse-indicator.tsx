"use client";

import { motion } from "framer-motion";
import { Wrench } from "lucide-react";
import { cn } from "@/lib/utils";

export type AgentState = "listening" | "thinking" | "speaking" | "tool_call" | "idle";

const LABEL: Record<AgentState, string> = {
  listening: "listening",
  thinking: "thinking",
  speaking: "speaking",
  tool_call: "tool call",
  idle: "idle",
};

const RING_COLOR: Record<AgentState, string> = {
  listening: "rgba(34, 211, 238, 0.55)",
  thinking: "rgba(34, 211, 238, 0.85)",
  speaking: "rgba(34, 211, 238, 1.0)",
  tool_call: "rgba(34, 211, 238, 0.85)",
  idle: "rgba(255, 255, 255, 0.25)",
};

const CORE_OPACITY: Record<AgentState, number> = {
  listening: 0.5,
  thinking: 0.7,
  speaking: 1.0,
  tool_call: 0.85,
  idle: 0.3,
};

/** Circular SVG pulse. State controls speed + intensity. */
export function PulseIndicator({ state, className }: { state: AgentState; className?: string }) {
  const isActive = state !== "idle";

  // Pulse cadence per state — gentle for listening, faster for thinking/tool_call,
  // steady glow for speaking.
  const ringDuration =
    state === "thinking" || state === "tool_call"
      ? 1.2
      : state === "speaking"
      ? 2.4
      : 2.0;

  const rotate = state === "thinking" || state === "tool_call";

  return (
    <div className={cn("flex flex-col items-center gap-3", className)}>
      <div className="relative h-28 w-28 sm:h-32 sm:w-32">
        {/* Outer expanding ring — quickens with state */}
        {isActive && (
          <motion.span
            key={`ring-${state}`}
            initial={{ scale: 0.6, opacity: 0.6 }}
            animate={{ scale: 1.4, opacity: 0 }}
            transition={{ duration: ringDuration, repeat: Infinity, ease: "easeOut" }}
            style={{ boxShadow: `0 0 28px ${RING_COLOR[state]}, inset 0 0 0 1px ${RING_COLOR[state]}` }}
            className="absolute inset-0 rounded-full"
          />
        )}
        {/* Mid ring */}
        <motion.span
          animate={
            isActive
              ? { rotate: rotate ? [0, 360] : 0, scale: [0.95, 1.05, 0.95] }
              : { rotate: 0, scale: 1 }
          }
          transition={
            isActive
              ? {
                  rotate: rotate ? { duration: 4, repeat: Infinity, ease: "linear" } : undefined,
                  scale: { duration: ringDuration, repeat: Infinity, ease: "easeInOut" },
                }
              : undefined
          }
          style={{ boxShadow: `inset 0 0 0 1px ${RING_COLOR[state]}` }}
          className="absolute inset-3 rounded-full"
        />
        {/* Core orb */}
        <motion.span
          animate={{ opacity: CORE_OPACITY[state] }}
          transition={{ duration: 0.4 }}
          style={{
            background:
              state === "idle"
                ? "radial-gradient(circle at center, rgba(255,255,255,0.15), transparent 70%)"
                : "radial-gradient(circle at center, rgba(34,211,238,0.8), rgba(34,211,238,0.18) 50%, transparent 75%)",
            filter: state === "speaking" ? "blur(2px)" : "blur(3px)",
          }}
          className="absolute inset-6 rounded-full"
        />
        {/* Tool overlay icon */}
        {state === "tool_call" && (
          <motion.span
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            className="absolute inset-0 flex items-center justify-center"
          >
            <Wrench className="h-4 w-4 text-cyan-200" strokeWidth={2} />
          </motion.span>
        )}
      </div>

      <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-white/50">
        {LABEL[state]}
      </span>
    </div>
  );
}
