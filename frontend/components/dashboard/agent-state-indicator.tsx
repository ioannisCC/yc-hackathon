"use client";

import { GlassCard } from "@/components/dashboard/glass-card";
import { PulseIndicator, type AgentState } from "@/components/dashboard/pulse-indicator";
import type { TranscriptChunk, ToolCallRecord } from "@/components/dashboard/live-transcript";

/** Infers the agent's current state from the most recent transcript chunk
 *  and tool-call activity, then renders the pulse visual. */
export function AgentStateIndicator({
  chunks,
  toolCalls,
  status,
}: {
  chunks: TranscriptChunk[];
  toolCalls: ToolCallRecord[];
  status: "in_progress" | "completed" | "failed" | "idle";
}) {
  const state = inferState(chunks, toolCalls, status);

  return (
    <GlassCard size="md" glow={state === "idle" ? "none" : "soft"}>
      <div className="flex flex-col items-center gap-4 py-2 sm:py-4">
        <PulseIndicator state={state} />
      </div>
    </GlassCard>
  );
}

function inferState(
  chunks: TranscriptChunk[],
  toolCalls: ToolCallRecord[],
  status: "in_progress" | "completed" | "failed" | "idle",
): AgentState {
  if (status !== "in_progress") return "idle";
  const lastChunk = chunks[chunks.length - 1];
  const lastTool = toolCalls[toolCalls.length - 1];
  const lastChunkTs = lastChunk?.ts ?? "";
  const lastToolTs = lastTool?.ts ?? "";

  // Most recent activity wins
  if (lastToolTs && lastToolTs > lastChunkTs) return "tool_call";
  if (!lastChunk) return "listening";
  if (lastChunk.role === "agent") return "speaking";
  return "thinking"; // caller just spoke; agent is reasoning
}
