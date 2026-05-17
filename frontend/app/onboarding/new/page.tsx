"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";

import { CyclingPlaceholder, DynamicIsland } from "@/components/dynamic-island";
import { LiquidButton } from "@/components/liquid-button";
import { LiquidInput } from "@/components/liquid-input";
import { OnboardingStepCard } from "@/components/onboarding-step-card";
import { useOnboarding } from "@/hooks/use-onboarding";

const EASE = [0.22, 1, 0.36, 1] as const;

export default function OnboardingNewPage() {
  const router = useRouter();
  const { phase, steps, activeIndex, business, error, submit } = useOnboarding();

  const [expanded, setExpanded] = useState(false);
  const [url, setUrl] = useState("");
  const [shake, setShake] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const cardsRef = useRef<HTMLDivElement>(null);

  // Focus the input the moment the island expands
  useEffect(() => {
    if (expanded) {
      const t = setTimeout(() => inputRef.current?.focus(), 220);
      return () => clearTimeout(t);
    }
  }, [expanded]);

  // Route to the live page after the POST resolves
  useEffect(() => {
    if (phase === "done" && business) {
      const t = setTimeout(() => router.push(`/onboarding/${business.id}`), 900);
      return () => clearTimeout(t);
    }
  }, [phase, business, router]);

  // Autoscroll the active step into the centered viewport
  useEffect(() => {
    if (phase !== "running") return;
    const target = cardsRef.current?.querySelector<HTMLElement>(
      `[data-step-id="${steps[activeIndex]?.id ?? ""}"]`,
    );
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [activeIndex, phase, steps]);

  useEffect(() => {
    if (phase === "error") {
      setShake(true);
      const t = setTimeout(() => setShake(false), 600);
      return () => clearTimeout(t);
    }
  }, [phase]);

  const handleSubmit = useCallback(
    (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      const trimmed = url.trim();
      if (!trimmed) {
        setShake(true);
        setTimeout(() => setShake(false), 600);
        return;
      }
      submit(trimmed);
    },
    [url, submit],
  );

  const islandMode: "collapsed" | "expanded" | "status" =
    phase === "paste"
      ? expanded
        ? "expanded"
        : "collapsed"
      : "status";

  const currentStep = steps[Math.min(activeIndex, steps.length - 1)];

  return (
    <main className="relative mx-auto flex min-h-screen w-full max-w-3xl flex-col items-center px-4 pt-[18vh] pb-24 sm:px-6 sm:pt-[22vh]">
      {/* HERO COPY — only while in paste state */}
      <AnimatePresence mode="wait">
        {phase === "paste" && (
          <motion.div
            key="hero"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.6, ease: EASE }}
            className="mb-10 text-center sm:mb-12"
          >
            <h1 className="text-balance bg-gradient-to-b from-white to-white/65 bg-clip-text text-4xl font-semibold leading-[1.05] tracking-tight text-transparent sm:text-6xl">
              Answer every call.
            </h1>
            <p className="mx-auto mt-4 max-w-xl text-balance text-sm font-normal leading-relaxed tracking-normal text-white/55 sm:mt-5 sm:text-base">
              Paste your business URL. In under five minutes, your business has
              a phone number staffed by an AI that books real appointments.
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* THE ISLAND */}
      <div className="w-full">
        <DynamicIsland mode={islandMode}>
          {islandMode === "collapsed" && (
            <button
              type="button"
              onClick={() => setExpanded(true)}
              className="flex h-full w-full items-center justify-center"
            >
              <CyclingPlaceholder />
            </button>
          )}

          {islandMode === "expanded" && (
            <form
              onSubmit={handleSubmit}
              className="flex w-full items-center gap-2 sm:gap-3"
            >
              <LiquidInput
                ref={inputRef}
                type="url"
                inputMode="url"
                autoComplete="off"
                spellCheck={false}
                required
                placeholder="https://your-business.com"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                shake={shake}
              />
              <LiquidButton type="submit" className="shrink-0">
                <span className="hidden sm:inline">Bring it live</span>
                <ArrowRight className="h-4 w-4 sm:hidden" />
              </LiquidButton>
            </form>
          )}

          {islandMode === "status" && currentStep && (
            <div className="flex w-full items-center gap-2.5 sm:gap-3 text-xs sm:text-sm">
              <span className="inline-flex h-2 w-2 shrink-0 animate-pulse rounded-full bg-cyan-300 shadow-[0_0_12px_rgba(34,211,238,0.9)]" />
              <span className="truncate font-medium tracking-tight text-white">
                {currentStep.label}
              </span>
              <span className="ml-auto shrink-0 font-mono text-[10px] sm:text-xs text-white/40">
                {Math.min(activeIndex + 1, steps.length)} / {steps.length}
              </span>
            </div>
          )}
        </DynamicIsland>

        {/* Inline error under the island */}
        <AnimatePresence>
          {phase === "error" && error && (
            <motion.p
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
              className="mt-4 text-center text-xs sm:text-sm font-normal tracking-normal text-red-400/90"
            >
              {error}
            </motion.p>
          )}
        </AnimatePresence>
      </div>

      {/* STEP CARDS — appear during running / done */}
      <AnimatePresence>
        {(phase === "running" || phase === "done") && (
          <motion.div
            ref={cardsRef}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5, ease: EASE }}
            className="mt-12 flex w-full max-w-xl flex-col gap-2.5 sm:mt-16 sm:gap-3"
          >
            {steps.map((step, i) => (
              <OnboardingStepCard
                key={step.id}
                step={step}
                index={i}
                isCurrent={i === activeIndex && phase === "running"}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}
