"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, onboardBusiness, type Business } from "@/lib/api";
import type { Step } from "@/components/onboarding-step-card";

export type Phase = "paste" | "running" | "done" | "error";

export type UseOnboardingResult = {
  phase: Phase;
  steps: Step[];
  activeIndex: number; // index of the "active" step, or steps.length when done
  business: Business | null;
  error: string | null;
  submit: (url: string) => void;
  reset: () => void;
};

/**
 * The backend POST is atomic — it runs all 6 steps then returns a Business.
 * We can't poll for intermediate state, so we drive the UI off a realistic
 * timer (durations sum to ~42s, matching observed onboarding latency) and
 * snap to "done" the moment the POST resolves. If the POST finishes early
 * we collapse remaining steps; if it's slow, the final step stays "active"
 * until the network completes.
 */

const STEP_BLUEPRINT: Array<Omit<Step, "status"> & { etaMs: number }> = [
  { id: "scrape",   label: "Reading the business site",     service: "Browser Use", etaMs: 22_000 },
  { id: "moss",     label: "Building knowledge index",      service: "Moss",        etaMs: 2_500 },
  { id: "inbox",    label: "Setting up email inbox",        service: "AgentMail",   etaMs: 2_500 },
  { id: "calcom",   label: "Wiring booking system",         service: "Cal.com",     etaMs: 5_500 },
  { id: "agent",    label: "Provisioning AI agent + phone", service: "AgentPhone",  etaMs: 6_000 },
  { id: "live",     label: "Live",                          service: "",            etaMs: 1_500 },
];

const initialSteps = (): Step[] =>
  STEP_BLUEPRINT.map((s) => ({
    id: s.id, label: s.label, service: s.service, status: "pending",
  }));

export function useOnboarding(): UseOnboardingResult {
  const [phase, setPhase] = useState<Phase>("paste");
  const [steps, setSteps] = useState<Step[]>(initialSteps);
  const [activeIndex, setActiveIndex] = useState(0);
  const [business, setBusiness] = useState<Business | null>(null);
  const [error, setError] = useState<string | null>(null);

  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clearTimers = useCallback(() => {
    timersRef.current.forEach((t) => clearTimeout(t));
    timersRef.current = [];
  }, []);

  useEffect(() => clearTimers, [clearTimers]);

  const reset = useCallback(() => {
    clearTimers();
    setPhase("paste");
    setSteps(initialSteps());
    setActiveIndex(0);
    setBusiness(null);
    setError(null);
  }, [clearTimers]);

  const submit = useCallback(
    (url: string) => {
      clearTimers();
      setPhase("running");
      setError(null);
      setBusiness(null);
      setSteps(initialSteps());
      setActiveIndex(0);

      // Step 0 starts active immediately
      setSteps((cur) => cur.map((s, i) => (i === 0 ? { ...s, status: "active" } : s)));

      // Schedule transitions for steps 0..N-2 (the final "Live" step is
      // gated on the POST response).
      let cumulative = 0;
      for (let i = 0; i < STEP_BLUEPRINT.length - 1; i++) {
        const blueprint = STEP_BLUEPRINT[i]!;
        cumulative += blueprint.etaMs;
        const t = setTimeout(() => {
          setSteps((cur) =>
            cur.map((s, idx) => {
              if (idx === i) return { ...s, status: "done" };
              if (idx === i + 1) return { ...s, status: "active" };
              return s;
            }),
          );
          setActiveIndex(i + 1);
        }, cumulative);
        timersRef.current.push(t);
      }

      // Fire the actual POST
      onboardBusiness(url)
        .then((biz) => {
          clearTimers();
          setBusiness(biz);
          setSteps((cur) => cur.map((s) => ({ ...s, status: "done" })));
          setActiveIndex(STEP_BLUEPRINT.length);
          setPhase("done");
        })
        .catch((e: unknown) => {
          clearTimers();
          let msg = "Something went wrong";
          if (e instanceof ApiError) {
            msg =
              typeof e.detail === "object" && e.detail
                ? JSON.stringify(e.detail).slice(0, 240)
                : `Backend ${e.status}`;
          } else if (e instanceof Error) {
            msg = e.message;
          }
          setError(msg);
          setPhase("error");
        });
    },
    [clearTimers],
  );

  return { phase, steps, activeIndex, business, error, submit, reset };
}
