"use client";

import { useEffect, useState } from "react";
import { getStats, type Stats } from "@/lib/api";

const POLL_MS = 5000;

export function useStats(businessId: string | null): Stats | null {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    if (!businessId) {
      setStats(null);
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      try {
        const s = await getStats(businessId);
        if (!cancelled) setStats(s);
      } catch {
        // Soft-fail — keep last value, retry on next tick.
      }
      if (!cancelled) timer = setTimeout(tick, POLL_MS);
    };

    void tick();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [businessId]);

  return stats;
}
