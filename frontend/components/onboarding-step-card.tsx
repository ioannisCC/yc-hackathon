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
      initial={{ opacity: 0, y: 16, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{
        duration: 0.6,
        delay: index * 0.08,
        ease: [0.22, 1, 0.36, 1],
      }}
      className={cn(
        "relative isolate w-full rounded-2xl border px-4 sm:px-5 py-3.5 sm:py-4",
        "backdrop-blur-md transition-[border-color,box-shadow,background-color] duration-500",
        isActive
          ? "border-cyan-300/40 bg-cyan-400/[0.05] shadow-[inset_0_0_36px_rgba(34,211,238,0.18),0_0_48px_rgba(34,211,238,0.18)]"
          : isDone
          ? "border-white/5 bg-white/[0.02] shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]"
          : "border-white/8 bg-white/[0.03] shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]",
      )}
    >
      <div className="flex items-center gap-3 sm:gap-4">
        <StatusIcon status={step.status} />
        <div className="min-w-0 flex-1">
          <p
            className={cn(
              "text-sm sm:text-[15px] font-medium leading-tight tracking-tight",
              isDone ? "text-white/55" : "text-white",
            )}
          >
            {step.label}
          </p>
          {!isDone && step.service && (
            <p className="mt-0.5 text-[11px] sm:text-xs font-normal tracking-[0.08em] uppercase text-white/35">
              {step.service}
            </p>
          )}
        </div>
        {isCurrent && (
          <span className="hidden sm:inline-flex shrink-0 items-center gap-1.5 rounded-full border border-cyan-300/30 bg-cyan-400/[0.08] px-2.5 py-0.5 text-[10px] uppercase tracking-[0.18em] text-cyan-200/90">
            <span className="h-1 w-1 animate-pulse rounded-full bg-cyan-300" />
            running
          </span>
        )}
      </div>

      {/* Refractive top edge */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-4 top-px h-px bg-gradient-to-r from-transparent via-white/15 to-transparent"
      />
    </motion.div>
  );
}

function StatusIcon({ status }: { status: StepStatus }) {
  const base =
    "flex h-7 w-7 sm:h-8 sm:w-8 shrink-0 items-center justify-center rounded-full border transition-colors";

  if (status === "done") {
    return (
      <div
        className={cn(
          base,
          "border-cyan-300/40 bg-cyan-300/15 shadow-[0_0_12px_rgba(34,211,238,0.35)]",
        )}
      >
        <Check className="h-3.5 w-3.5 text-cyan-100" strokeWidth={3} />
      </div>
    );
  }
  if (status === "active") {
    return (
      <div
        className={cn(
          base,
          "border-cyan-300/55 bg-cyan-300/15 shadow-[0_0_18px_rgba(34,211,238,0.55)]",
        )}
      >
        <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan-100" />
      </div>
    );
  }
  return (
    <div className={cn(base, "border-white/15 bg-white/5")}>
      <span className="h-1.5 w-1.5 rounded-full bg-white/30" />
    </div>
  );
}
