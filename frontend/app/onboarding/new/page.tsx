"use client";

import { AnimatePresence, motion } from "framer-motion";
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

export default function OnboardingNewPage() {
  const router = useRouter();
  const { phase, steps, activeIndex, business, error, submit } = useOnboarding();

  const [expanded, setExpanded] = useState(false);
  const [url, setUrl] = useState("");
  const [shake, setShake] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const cardsRef = useRef<HTMLDivElement>(null);

  // When the dynamic island opens, focus the input
  useEffect(() => {
    if (expanded) inputRef.current?.focus();
  }, [expanded]);

  // After the POST resolves, route to /onboarding/{id} for the "live" state.
  useEffect(() => {
    if (phase === "done" && business) {
      const t = setTimeout(() => router.push(`/onboarding/${business.id}`), 900);
      return () => clearTimeout(t);
    }
  }, [phase, business, router]);

  // Autoscroll so the currently active card stays vertically centered.
  useEffect(() => {
    if (phase !== "running") return;
    const target = cardsRef.current?.querySelector<HTMLElement>(
      `[data-step-id="${steps[activeIndex]?.id ?? ""}"]`,
    );
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [activeIndex, phase, steps]);

  // Brief shake on error
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

  const islandMode =
    phase === "paste"
      ? expanded
        ? "expanded"
        : "collapsed"
      : "status";

  const currentStep = steps[Math.min(activeIndex, steps.length - 1)];

  return (
    <main className="relative flex min-h-screen flex-col items-center px-6 pt-[18vh] pb-32">
      {/* HERO copy — only while in paste state */}
      <AnimatePresence>
        {phase === "paste" && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            className="mb-10 max-w-2xl text-center"
          >
            <h1 className="text-balance text-5xl font-semibold tracking-tight text-white sm:text-6xl">
              Answer every call.
            </h1>
            <p className="mt-4 text-base font-normal tracking-normal text-white/55 sm:text-lg">
              Paste your business URL. Five minutes later, your business has a
              phone number staffed by an AI that books real appointments.
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Dynamic Island */}
      <div className="w-full max-w-3xl">
        <DynamicIsland mode={islandMode}>
          {islandMode === "collapsed" && (
            <button
              type="button"
              onClick={() => setExpanded(true)}
              className="w-full"
            >
              <CyclingPlaceholder />
            </button>
          )}

          {islandMode === "expanded" && (
            <form
              onSubmit={handleSubmit}
              className="flex w-full items-center gap-3"
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
              <LiquidButton type="submit">Bring it live</LiquidButton>
            </form>
          )}

          {islandMode === "status" && currentStep && (
            <div className="flex w-full items-center gap-3 px-1 text-sm">
              <span className="inline-flex h-2 w-2 animate-pulse rounded-full bg-cyan-300 shadow-[0_0_12px_rgba(34,211,238,0.9)]" />
              <span className="font-medium tracking-wide text-white">
                {currentStep.label}
              </span>
              <span className="ml-auto text-white/40">
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
              className="mt-4 text-center text-sm font-normal tracking-normal text-red-400/90"
            >
              {error}
            </motion.p>
          )}
        </AnimatePresence>
      </div>

      {/* Step cards — appear during running and done phases */}
      <AnimatePresence>
        {(phase === "running" || phase === "done") && (
          <motion.div
            ref={cardsRef}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4 }}
            className="mt-16 flex w-full max-w-xl flex-col gap-3"
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
