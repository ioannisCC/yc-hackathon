"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef } from "react";
import { GlassCard } from "@/components/dashboard/glass-card";
import { cn } from "@/lib/utils";

export type TranscriptChunk = {
  role: "caller" | "agent";
  text: string;
  ts?: string;
  tool_call?: { name: string; args?: Record<string, unknown> };
};

export type ToolCallRecord = {
  name: string;
  args?: Record<string, unknown>;
  ts?: string;
};

/** Renders the unified call timeline: caller bubbles (right, neutral),
 *  agent bubbles (left, cyan-tinted), inline tool-call chips between turns.
 *  Autoscrolls to the newest line; shows a "listening..." dot pulse when
 *  the call is in_progress with no recent agent chunk. */
export function LiveTranscript({
  chunks,
  toolCalls,
  status,
}: {
  chunks: TranscriptChunk[];
  toolCalls: ToolCallRecord[];
  status: "in_progress" | "completed" | "failed" | "idle";
}) {
  const scrollerRef = useRef<HTMLDivElement>(null);

  // Merge transcript + tool calls into a single timeline ordered by ts.
  const timeline = mergeTimeline(chunks, toolCalls);

  // Autoscroll to the bottom whenever new items arrive
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [timeline.length]);

  const showListening =
    status === "in_progress" &&
    (timeline.length === 0 || timeline[timeline.length - 1]?.kind === "caller");

  return (
    <GlassCard size="md" className="flex h-full min-h-[24rem] flex-col">
      <div className="mb-3 flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/45">
          Live transcript
        </span>
        <span
          className={cn(
            "font-mono text-[10px] uppercase tracking-[0.22em]",
            status === "in_progress" ? "text-cyan-300" : "text-white/35",
          )}
        >
          {status === "in_progress" ? "● live" : status}
        </span>
      </div>

      <div
        ref={scrollerRef}
        className="flex-1 overflow-y-auto pr-1 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden"
      >
        {timeline.length === 0 && status !== "in_progress" && (
          <div className="flex h-full items-center justify-center">
            <p className="text-center text-xs text-white/35">
              Waiting for the first call.
            </p>
          </div>
        )}

        <div className="flex flex-col gap-2.5">
          <AnimatePresence initial={false}>
            {timeline.map((item, i) => {
              if (item.kind === "tool") {
                return <ToolChip key={`${i}-${item.name}`} call={item} />;
              }
              return <Bubble key={`${i}-${item.kind}`} role={item.kind} text={item.text} />;
            })}
          </AnimatePresence>

          {showListening && <ListeningDots />}
        </div>
      </div>
    </GlassCard>
  );
}

/* ---------- timeline merge ---------- */

type TimelineItem =
  | { kind: "caller"; text: string; ts: string }
  | { kind: "agent"; text: string; ts: string }
  | { kind: "tool"; name: string; args?: Record<string, unknown>; ts: string };

function mergeTimeline(
  chunks: TranscriptChunk[],
  toolCalls: ToolCallRecord[],
): TimelineItem[] {
  const items: TimelineItem[] = [];
  for (const c of chunks) {
    items.push({ kind: c.role, text: c.text, ts: c.ts ?? "" });
  }
  for (const t of toolCalls) {
    items.push({ kind: "tool", name: t.name, args: t.args, ts: t.ts ?? "" });
  }
  items.sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0));
  return items;
}

/* ---------- bubble ---------- */

function Bubble({ role, text }: { role: "caller" | "agent"; text: string }) {
  const isAgent = role === "agent";
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className={cn("flex w-full", isAgent ? "justify-start" : "justify-end")}
    >
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed backdrop-blur-md",
          isAgent
            ? "bg-cyan-400/[0.08] text-cyan-50 shadow-[inset_0_0_0_1px_rgba(34,211,238,0.25),0_0_18px_rgba(34,211,238,0.10)]"
            : "bg-white/[0.06] text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08),0_4px_14px_rgba(0,0,0,0.30)]",
        )}
      >
        {text}
      </div>
    </motion.div>
  );
}

/* ---------- tool chip ---------- */

function ToolChip({
  call,
}: {
  call: { name: string; args?: Record<string, unknown> };
}) {
  const argStr = call.args
    ? Object.entries(call.args)
        .slice(0, 3)
        .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
        .join(", ")
    : "";
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25 }}
      className="my-1 flex justify-center"
    >
      <span className="inline-flex max-w-full items-center gap-2 truncate rounded-full border border-cyan-300/25 bg-cyan-400/[0.05] px-3 py-1 font-mono text-[11px] text-cyan-200/85">
        <span className="text-cyan-300/60">↳</span>
        <span className="truncate">
          {call.name}({argStr})
        </span>
      </span>
    </motion.div>
  );
}

/* ---------- listening dots ---------- */

function ListeningDots() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex justify-start"
    >
      <div className="flex items-center gap-1 rounded-2xl bg-cyan-400/[0.06] px-3.5 py-3 shadow-[inset_0_0_0_1px_rgba(34,211,238,0.20)]">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            animate={{ opacity: [0.3, 1, 0.3], y: [0, -2, 0] }}
            transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.15, ease: "easeInOut" }}
            className="h-1.5 w-1.5 rounded-full bg-cyan-300"
          />
        ))}
      </div>
    </motion.div>
  );
}
