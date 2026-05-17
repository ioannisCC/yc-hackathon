"use client";

import { motion } from "framer-motion";
import { Phone } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { DynamicIsland } from "@/components/dynamic-island";
import { LiquidButton } from "@/components/liquid-button";
import { getBusiness, type Business } from "@/lib/api";
import { formatPhone } from "@/lib/utils";

type Props = { params: { id: string } };

const EASE = [0.22, 1, 0.36, 1] as const;

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
    <main className="relative mx-auto flex min-h-screen w-full max-w-3xl flex-col items-center px-4 pt-[14vh] pb-24 sm:px-6 sm:pt-[18vh]">
      <div className="w-full">
        <DynamicIsland mode="status">
          <div className="flex w-full items-center gap-3 text-xs sm:text-sm">
            <span className="inline-flex h-2 w-2 shrink-0 rounded-full bg-cyan-300 shadow-[0_0_12px_rgba(34,211,238,0.9)]" />
            <span className="truncate font-medium tracking-tight text-white">
              {business ? `${business.name} · Live` : "Loading…"}
            </span>
          </div>
        </DynamicIsland>
      </div>

      {business && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: EASE }}
          className="mt-16 flex w-full flex-col items-center text-center sm:mt-24"
        >
          <span className="text-[10px] uppercase tracking-[0.32em] text-white/40 sm:text-xs">
            your number
          </span>

          <motion.div
            initial={{ opacity: 0, scale: 0.94 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.9, delay: 0.15, ease: EASE }}
            className="mt-4 bg-gradient-to-b from-white to-cyan-100/70 bg-clip-text font-sans text-4xl font-semibold leading-none tracking-tight text-transparent sm:mt-6 sm:text-6xl md:text-7xl"
            style={{
              filter: "drop-shadow(0 0 32px rgba(34,211,238,0.45)) drop-shadow(0 0 80px rgba(34,211,238,0.25))",
            }}
          >
            {formatPhone(business.phone_number)}
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.5 }}
            className="mt-8 flex flex-col items-center gap-3 sm:mt-12 sm:flex-row"
          >
            <LiquidButton
              size="lg"
              onClick={() => {
                window.location.href = `tel:${business.phone_number}`;
              }}
            >
              <Phone className="h-4 w-4" />
              Call this number
            </LiquidButton>
            <Link
              href="/onboarding/new"
              className="rounded-full border border-white/10 bg-white/[0.04] px-5 py-2.5 text-sm font-normal tracking-wide text-white/65 backdrop-blur-md transition-colors hover:border-white/20 hover:bg-white/[0.08] hover:text-white"
            >
              Onboard another
            </Link>
          </motion.div>

          <p className="mt-8 max-w-md text-balance text-xs leading-relaxed text-white/45 sm:mt-10 sm:text-sm">
            Your AI receptionist is answering this number now. Call it from your
            phone — it&apos;ll book real appointments and send email
            confirmations.
          </p>
        </motion.section>
      )}

      {error && !business && (
        <p className="mt-16 text-center text-sm text-red-400/90">{error}</p>
      )}
    </main>
  );
}
