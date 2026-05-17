"use client";

import { useEffect, useState } from "react";
import { listBusinessCalls, type CallSummary } from "@/lib/api";

const POLL_MS = 2500;

/** Polls /businesses/{id}/calls; returns the most recent in-progress call
 *  (or null when idle). Lets the dashboard switch between PhoneNumberHero
 *  and LiveTranscript without an explicit subscription mechanism. */
export function useActiveCall(businessId: string | null): {
  activeCall: CallSummary | null;
  recentCalls: CallSummary[];
} {
  const [recentCalls, setRecentCalls] = useState<CallSummary[]>([]);

  useEffect(() => {
    if (!businessId) {
      setRecentCalls([]);
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      try {
        const calls = await listBusinessCalls(businessId, 5);
        if (!cancelled) setRecentCalls(calls);
      } catch {
        /* ignore transient failures */
      }
      if (!cancelled) timer = setTimeout(tick, POLL_MS);
    };

    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [businessId]);

  const activeCall = recentCalls.find((c) => c.status === "in_progress") ?? null;
  return { activeCall, recentCalls };
}
