"use client";

import { motion } from "framer-motion";
import { Phone } from "lucide-react";
import { LiquidButton } from "@/components/liquid-button";
import { formatPhone } from "@/lib/utils";

const EASE = [0.22, 1, 0.36, 1] as const;

/** Idle-state centerpiece. Big phone number + tel: CTA. */
export function PhoneNumberHero({ phoneNumber, businessName }: { phoneNumber: string; businessName?: string }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.8, ease: EASE }}
      className="flex flex-col items-center text-center"
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
          filter:
            "drop-shadow(0 0 32px rgba(34,211,238,0.45)) drop-shadow(0 0 80px rgba(34,211,238,0.25))",
        }}
      >
        {formatPhone(phoneNumber)}
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.5 }}
        className="mt-8 sm:mt-10"
      >
        <LiquidButton
          size="lg"
          onClick={() => {
            window.location.href = `tel:${phoneNumber}`;
          }}
        >
          <Phone className="h-4 w-4" />
          Call this number
        </LiquidButton>
      </motion.div>

      <p className="mt-8 max-w-md text-balance text-xs leading-relaxed text-white/45 sm:mt-10 sm:text-sm">
        {businessName ? (
          <>Your AI receptionist for <span className="text-white/65">{businessName}</span> is live. Call the number from your phone — it&apos;ll book real appointments and email confirmations.</>
        ) : (
          <>Your AI receptionist is live. Call the number from your phone — it&apos;ll book real appointments and email confirmations.</>
        )}
      </p>
    </motion.section>
  );
}
