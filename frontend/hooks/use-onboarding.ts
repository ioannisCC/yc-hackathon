"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  ApiError,
  fetchOnboardingStatus,
  startOnboarding,
  type OnboardingStatus,
} from "@/lib/api";
import type { Step } from "@/components/onboarding-step-card";

export type Phase = "paste" | "running" | "done" | "error";

export type UseOnboardingResult = {
  phase: Phase;
  steps: Step[];
  activeIndex: number;
  businessId: string | null;
  failedStep: string | null;
  error: string | null;
  submit: (url: string) => void;
  reset: () => void;
};

/** Polls the backend's real /onboarding-status endpoint every 500ms while
 *  the pipeline runs. Each step transition advances the 6-card UI in lockstep
 *  with the actual backend state. */

// Maps backend step keys → UI step blueprint
const BLUEPRINT: Array<Omit<Step, "status"> & { key: string }> = [
  { key: "scraping", id: "scraping", label: "Reading the business site",     service: "Browser Use" },
  { key: "moss",     id: "moss",     label: "Building knowledge index",      service: "Moss" },
  { key: "inbox",    id: "inbox",    label: "Setting up email inbox",        service: "AgentMail" },
  { key: "calcom",   id: "calcom",   label: "Wiring booking system",         service: "Cal.com" },
  { key: "agent",    id: "agent",    label: "Provisioning AI agent + phone", service: "AgentPhone" },
  { key: "live",     id: "live",     label: "Live",                          service: "" },
];

const POLL_MS = 500;

function initialSteps(): Step[] {
  return BLUEPRINT.map((s) => ({
    id: s.id, label: s.label, service: s.service, status: "pending",
  }));
}

function stepsFromStatus(status: OnboardingStatus): { steps: Step[]; activeIndex: number } {
  const completed = new Set(status.completed_steps);
  const steps: Step[] = BLUEPRINT.map((b) => {
    if (completed.has(b.key)) return { id: b.id, label: b.label, service: b.service, status: "done" };
    if (b.key === status.current_step) return { id: b.id, label: b.label, service: b.service, status: "active" };
    return { id: b.id, label: b.label, service: b.service, status: "pending" };
  });
  const activeIndex = BLUEPRINT.findIndex((b) => b.key === status.current_step);
  return { steps, activeIndex: activeIndex < 0 ? steps.length : activeIndex };
}

export function useOnboarding(): UseOnboardingResult {
  const [phase, setPhase] = useState<Phase>("paste");
  const [steps, setSteps] = useState<Step[]>(initialSteps);
  const [activeIndex, setActiveIndex] = useState(0);
  const [businessId, setBusinessId] = useState<string | null>(null);
  const [failedStep, setFailedStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelledRef = useRef(false);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      cancelledRef.current = true;
      stopPolling();
    };
  }, [stopPolling]);

  const reset = useCallback(() => {
    stopPolling();
    setPhase("paste");
    setSteps(initialSteps());
    setActiveIndex(0);
    setBusinessId(null);
    setFailedStep(null);
    setError(null);
  }, [stopPolling]);

  const poll = useCallback(
    async (id: string): Promise<void> => {
      if (cancelledRef.current) return;
      try {
        const status = await fetchOnboardingStatus(id);

        if (status.current_step === "failed") {
          stopPolling();
          const stepKey = status.error?.step ?? "unknown";
          const message = status.error?.message ?? "Onboarding failed";
          setFailedStep(stepKey);
          setError(message);
          // Mark the failed step's UI card as "active" so the red treatment lands on it
          const idx = BLUEPRINT.findIndex((b) => b.key === stepKey);
          setSteps((cur) =>
            cur.map((s, i) =>
              i === idx ? { ...s, status: "active" } : s,
            ),
          );
          setActiveIndex(idx < 0 ? 0 : idx);
          setPhase("error");
          return;
        }

        if (status.current_step === "done") {
          stopPolling();
          setSteps((cur) => cur.map((s) => ({ ...s, status: "done" })));
          setActiveIndex(BLUEPRINT.length);
          setPhase("done");
          return;
        }

        const { steps: nextSteps, activeIndex: nextActive } = stepsFromStatus(status);
        setSteps(nextSteps);
        setActiveIndex(nextActive);

        pollTimerRef.current = setTimeout(() => void poll(id), POLL_MS);
      } catch (e) {
        // Transient — retry with a slight backoff. Hard error after many failures.
        pollTimerRef.current = setTimeout(() => void poll(id), POLL_MS * 4);
      }
    },
    [stopPolling],
  );

  const submit = useCallback(
    async (url: string) => {
      stopPolling();
      setPhase("running");
      setError(null);
      setFailedStep(null);
      setSteps(initialSteps());
      setActiveIndex(0);

      // Step 0 starts active immediately
      setSteps((cur) => cur.map((s, i) => (i === 0 ? { ...s, status: "active" } : s)));

      try {
        const { id } = await startOnboarding(url);
        setBusinessId(id);
        void poll(id);
      } catch (e: unknown) {
        let msg = "Couldn't reach the backend";
        if (e instanceof ApiError) {
          msg = typeof e.detail === "object" && e.detail
            ? JSON.stringify(e.detail).slice(0, 240)
            : `Backend ${e.status}`;
        } else if (e instanceof Error) {
          msg = e.message;
        }
        setError(msg);
        setPhase("error");
      }
    },
    [stopPolling, poll],
  );

  return { phase, steps, activeIndex, businessId, failedStep, error, submit, reset };
}
