"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { useEffect, useState } from "react";

import { DynamicIsland } from "@/components/dynamic-island";
import { LiquidButton } from "@/components/liquid-button";
import { getBusiness, type Business } from "@/lib/api";
import { formatPhone } from "@/lib/utils";

type Props = { params: { id: string } };

export default function OnboardingLivePage({ params }: Props) {
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

  return (
    <main className="relative flex min-h-screen flex-col items-center px-6 pt-[14vh] pb-32">
      <div className="w-full max-w-3xl">
        <DynamicIsland mode="status">
          <div className="flex w-full items-center gap-3 px-1 text-sm">
            <span className="inline-flex h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_12px_rgba(34,211,238,0.9)]" />
            <span className="font-medium tracking-wide text-white">
              {business ? `${business.name} · Live` : "Loading…"}
            </span>
          </div>
        </DynamicIsland>
      </div>

      {business && (
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          className="mt-20 flex flex-col items-center text-center"
        >
          <span className="text-xs uppercase tracking-[0.32em] text-white/40">
            your number
          </span>
          <motion.div
            initial={{ opacity: 0, scale: 0.94 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{
              duration: 0.9,
              delay: 0.15,
              ease: [0.22, 1, 0.36, 1],
            }}
            className="mt-6 font-sans text-6xl font-semibold tracking-tight text-white sm:text-7xl"
            style={{
              textShadow:
                "0 0 30px rgba(34,211,238,0.45), 0 0 80px rgba(34,211,238,0.25)",
            }}
          >
            {formatPhone(business.phone_number)}
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.5 }}
            className="mt-10 flex items-center gap-3"
          >
            <LiquidButton
              onClick={() => {
                window.location.href = `tel:${business.phone_number}`;
              }}
            >
              Call this number
            </LiquidButton>
            <Link
              href="/onboarding/new"
              className="rounded-full border border-white/10 bg-white/5 px-5 py-2.5 text-sm font-normal tracking-wide text-white/70 transition-colors hover:border-white/20 hover:bg-white/10 hover:text-white"
            >
              Onboard another
            </Link>
          </motion.div>

          <p className="mt-8 max-w-md text-sm font-normal tracking-normal text-white/45">
            Your AI receptionist is answering this number now. Call it from your
            phone — it&apos;ll book real appointments and send email
            confirmations.
          </p>
        </motion.div>
      )}

      {error && !business && (
        <p className="mt-20 text-center text-sm text-red-400/90">{error}</p>
      )}
    </main>
  );
}
