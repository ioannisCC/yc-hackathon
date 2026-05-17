"use client";

import { motion } from "framer-motion";
import { GlassCard } from "@/components/dashboard/glass-card";
import { CountUp } from "@/components/dashboard/count-up";

export type Stats = {
  calls_today: number;
  bookings_today: number;
  escalations_today: number;
};

export function StatsStrip({ stats }: { stats: Stats | null }) {
  const cards = [
    { label: "Calls today", value: stats?.calls_today ?? 0 },
    { label: "Bookings made", value: stats?.bookings_today ?? 0 },
    { label: "Escalations", value: stats?.escalations_today ?? 0 },
  ];

  return (
    <div className="grid w-full grid-cols-3 gap-2.5 sm:gap-3">
      {cards.map((c, i) => (
        <motion.div
          key={c.label}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: i * 0.06, ease: [0.22, 1, 0.36, 1] }}
        >
          <GlassCard size="sm" className="flex flex-col gap-1">
            <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/45">
              {c.label}
            </span>
            <span className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
              <CountUp value={c.value} />
            </span>
          </GlassCard>
        </motion.div>
      ))}
    </div>
  );
}
