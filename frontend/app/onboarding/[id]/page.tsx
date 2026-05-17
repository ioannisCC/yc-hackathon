"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";

import { ActivityFeed } from "@/components/dashboard/activity-feed";
import { AgentStateIndicator } from "@/components/dashboard/agent-state-indicator";
import { BusinessHeader } from "@/components/dashboard/business-header";
import { LiveTranscript } from "@/components/dashboard/live-transcript";
import { PhoneNumberHero } from "@/components/dashboard/phone-number-hero";
import { StatsStrip } from "@/components/dashboard/stats-strip";
import { useActiveCall } from "@/hooks/use-active-call";
import { useLiveCall } from "@/hooks/use-live-call";
import { useStats } from "@/hooks/use-stats";
import { getBusiness, type Business } from "@/lib/api";

type Props = { params: { id: string } };

const EASE = [0.22, 1, 0.36, 1] as const;

export default function DashboardPage({ params }: Props) {
  const [business, setBusiness] = useState<Business | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getBusiness(params.id)
      .then((b) => {
        if (cancelled) return;
        if (!b) setError("That business hasn't finished setting up yet.");
        else setBusiness(b);
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Unknown error"),
      );
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  const { activeCall } = useActiveCall(business?.id ?? null);
  const live = useLiveCall(activeCall?.id ?? null);
  const stats = useStats(business?.id ?? null);

  const ready =
    business !== null &&
    business.phone_number !== null &&
    business.name !== null;

  return (
    <main className="relative mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-4 px-4 pt-[12vh] pb-12 sm:gap-5 sm:px-6 sm:pt-[14vh]">
      {!ready && (
        <p className="mt-20 text-center text-sm text-white/55">
          {error ?? "Loading…"}
        </p>
      )}

      {ready && business !== null && business.phone_number !== null && business.name !== null && (
        <>
          {/* Header strip */}
          <BusinessHeader
            name={business.name}
            phoneNumber={business.phone_number}
            isLive={activeCall !== null}
          />

          {/* Centerpiece — morphs between idle (hero) and live (3-column) */}
          <AnimatePresence mode="wait">
            {activeCall === null ? (
              <motion.div
                key="idle"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.5, ease: EASE }}
                className="mt-8 flex flex-1 flex-col items-center justify-center sm:mt-12"
              >
                <PhoneNumberHero
                  phoneNumber={business.phone_number}
                  businessName={business.name}
                />
              </motion.div>
            ) : (
              <motion.div
                key="live"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }}
                transition={{ duration: 0.6, ease: EASE }}
                className="grid grid-cols-1 gap-3 lg:grid-cols-[18rem_minmax(0,1fr)_22rem] sm:gap-4"
              >
                <div className="order-2 lg:order-1">
                  <AgentStateIndicator
                    chunks={live.chunks}
                    toolCalls={live.toolCalls}
                    status={live.status}
                  />
                </div>
                <div className="order-1 lg:order-2">
                  <LiveTranscript
                    chunks={live.chunks}
                    toolCalls={live.toolCalls}
                    status={live.status}
                  />
                </div>
                <div className="order-3">
                  <ActivityFeed toolCalls={live.toolCalls} />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Stats strip */}
          <StatsStrip stats={stats} />
        </>
      )}
    </main>
  );
}
