"use client";

import { motion } from "framer-motion";
import { Check, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export type StepStatus = "pending" | "active" | "done";

export type Step = {
  id: string;
  label: string;
  service: string;
  status: StepStatus;
};

export function OnboardingStepCard({
  step,
  index,
  isCurrent,
}: {
  step: Step;
  index: number;
  isCurrent: boolean;
}) {
  const isDone = step.status === "done";
  const isActive = step.status === "active";

  return (
    <motion.div
      layout
      data-step-id={step.id}
      initial={{ opacity: 0, y: 18, scale: 0.96 }}
      animate={{
        opacity: 1,
        y: 0,
        scale: isDone ? 0.98 : 1,
        height: isDone ? 64 : 96,
      }}
      transition={{
        duration: 0.6,
        delay: index * 0.08,
        ease: [0.22, 1, 0.36, 1],
      }}
      className={cn(
        "relative w-full overflow-hidden rounded-2xl border px-5",
        "bg-[color-mix(in_oklab,white_3%,transparent)] backdrop-blur-xl",
        "transition-colors duration-500",
        isActive
          ? "border-cyan-300/45 shadow-[inset_0_0_30px_rgba(34,211,238,0.18),0_0_40px_rgba(34,211,238,0.20)]"
          : "border-white/8 shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_4px_24px_rgba(0,0,0,0.35)]",
      )}
    >
      <div className="flex h-full items-center gap-4">
        <StatusIcon status={step.status} />
        <div className="flex flex-col gap-0.5 min-w-0">
          <span
            className={cn(
              "text-base font-medium tracking-tight",
              isDone ? "text-white/55" : "text-white",
            )}
          >
            {step.label}
          </span>
          {!isDone && (
            <span className="text-xs font-normal tracking-wide text-white/40">
              {step.service}
            </span>
          )}
        </div>
        {isCurrent && (
          <motion.span
            aria-hidden
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="ml-auto text-[10px] uppercase tracking-[0.18em] text-cyan-300/80"
          >
            in progress
          </motion.span>
        )}
      </div>

      {/* refractive top-edge */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-3 top-px h-px bg-gradient-to-r from-transparent via-white/25 to-transparent"
      />
    </motion.div>
  );
}

function StatusIcon({ status }: { status: StepStatus }) {
  if (status === "done") {
    return (
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-cyan-300/40 bg-cyan-300/10">
        <Check className="h-3.5 w-3.5 text-cyan-200" strokeWidth={3} />
      </div>
    );
  }
  if (status === "active") {
    return (
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-cyan-300/55 bg-cyan-300/15">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan-200" />
      </div>
    );
  }
  return (
    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-white/15 bg-white/5">
      <span className="h-1.5 w-1.5 rounded-full bg-white/30" />
    </div>
  );
}
