"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Calendar, Mail } from "lucide-react";
import { GlassCard } from "@/components/dashboard/glass-card";
import type { ToolCallRecord } from "@/components/dashboard/live-transcript";

type BookingActivity = {
  kind: "booking";
  id: string;
  customerName: string;
  service: string;
  startISO: string;
};

type EmailActivity = {
  kind: "email";
  id: string;
  subject: string;
  recipient: string;
};

type Activity = BookingActivity | EmailActivity;

/** Derives a list of activity cards from the call's tool_calls stream.
 *  - book_appointment → BookingCard + EmailCard (the booking triggers a
 *    confirmation send in the backend so we surface both visually).
 *  - send_email / reply_to_message → EmailCard. */
export function ActivityFeed({ toolCalls }: { toolCalls: ToolCallRecord[] }) {
  const activities = deriveActivities(toolCalls);

  return (
    <GlassCard size="md" className="flex h-full min-h-[24rem] flex-col">
      <div className="mb-3 flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/45">
          Activity
        </span>
        <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/35">
          {activities.length}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
        {activities.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-center text-xs text-white/35">
              Bookings and emails appear here as they happen.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-2.5">
            <AnimatePresence initial={false}>
              {activities.map((a) =>
                a.kind === "booking" ? <BookingCard key={a.id} a={a} /> : <EmailCard key={a.id} a={a} />,
              )}
            </AnimatePresence>
          </div>
        )}
      </div>
    </GlassCard>
  );
}

/* ---------- derive ---------- */

function deriveActivities(toolCalls: ToolCallRecord[]): Activity[] {
  const out: Activity[] = [];
  // newest first
  const reversed = [...toolCalls].reverse();
  reversed.forEach((tc, idx) => {
    const args = (tc.args ?? {}) as Record<string, unknown>;
    if (tc.name === "book_appointment") {
      out.push({
        kind: "booking",
        id: `b-${idx}-${tc.ts ?? ""}`,
        customerName: String(args.caller_name ?? "Caller"),
        service: String(args.service_name ?? "Appointment"),
        startISO: String(args.start_iso ?? ""),
      });
      // Booking confirmation email is sent automatically — surface it too.
      out.push({
        kind: "email",
        id: `e-${idx}-${tc.ts ?? ""}`,
        subject: `Booking confirmed — ${String(args.service_name ?? "Appointment")}`,
        recipient: String(args.caller_email ?? "—"),
      });
    } else if (tc.name === "send_email" || tc.name === "reply_to_message") {
      out.push({
        kind: "email",
        id: `e-${idx}-${tc.ts ?? ""}`,
        subject: String(args.subject ?? "Email sent"),
        recipient: String(args.to ?? args.recipient ?? "—"),
      });
    }
  });
  return out;
}

/* ---------- cards ---------- */

const ARRIVE = {
  initial: { opacity: 0, x: 32, boxShadow: "0 0 32px rgba(34,211,238,0.45)" },
  animate: { opacity: 1, x: 0, boxShadow: "0 0 0px rgba(34,211,238,0)" },
  exit: { opacity: 0, x: -16 },
  transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] as const },
};

function BookingCard({ a }: { a: BookingActivity }) {
  return (
    <motion.div layout {...ARRIVE} className="rounded-xl border border-white/10 bg-white/[0.04] p-3 backdrop-blur-md">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-cyan-300/35 bg-cyan-400/10">
          <Calendar className="h-3.5 w-3.5 text-cyan-200" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-white">{a.customerName}</p>
          <p className="truncate text-xs text-white/55">{a.service}</p>
          {a.startISO && (
            <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.15em] text-white/45">
              {formatBookingTime(a.startISO)}
            </p>
          )}
        </div>
        <span className="shrink-0 font-mono text-[9px] uppercase tracking-[0.22em] text-white/30">
          Cal.com
        </span>
      </div>
    </motion.div>
  );
}

function EmailCard({ a }: { a: EmailActivity }) {
  return (
    <motion.div layout {...ARRIVE} className="rounded-xl border border-white/10 bg-white/[0.04] p-3 backdrop-blur-md">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-white/15 bg-white/5">
          <Mail className="h-3.5 w-3.5 text-white/80" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-white">{a.subject}</p>
          <p className="truncate text-xs text-white/55">{a.recipient}</p>
        </div>
        <span className="shrink-0 font-mono text-[9px] uppercase tracking-[0.22em] text-white/30">
          AgentMail
        </span>
      </div>
    </motion.div>
  );
}

function formatBookingTime(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
