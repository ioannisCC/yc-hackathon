"use client";

import { motion } from "framer-motion";
import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type LiquidInputProps = InputHTMLAttributes<HTMLInputElement> & {
  shake?: boolean;
};

/** Sister to LiquidButton — same refractive glass surface, full-width container,
 *  cyan border + glow when focus is inside, shake on error. */
export const LiquidInput = forwardRef<HTMLInputElement, LiquidInputProps>(
  function LiquidInput({ className, shake, ...rest }, ref) {
    return (
      <motion.div
        animate={shake ? { x: [0, -8, 8, -6, 6, -3, 3, 0] } : { x: 0 }}
        transition={{ duration: 0.5 }}
        className={cn(
          "group relative isolate flex w-full items-center rounded-full",
          "transition-shadow duration-300",
          className,
        )}
      >
        {/* Refractive lens layer */}
        <span
          aria-hidden
          className="absolute inset-0 -z-10 rounded-full bg-white/[0.06] backdrop-blur-xl"
          style={{ backdropFilter: "url(#liquid-glass) blur(12px) saturate(140%)" }}
        />

        {/* Edge + glow stack — gains a cyan ring when focus lands inside */}
        <span
          aria-hidden
          className={cn(
            "absolute inset-0 rounded-full",
            "shadow-[inset_0_1px_0_rgba(255,255,255,0.20),inset_0_-1px_0_rgba(0,0,0,0.50),inset_0_0_0_1px_rgba(255,255,255,0.10),0_8px_30px_rgba(0,0,0,0.45)]",
            "group-focus-within:shadow-[inset_0_1px_0_rgba(255,255,255,0.25),inset_0_-1px_0_rgba(0,0,0,0.50),inset_0_0_0_1px_rgba(34,211,238,0.55),0_0_30px_rgba(34,211,238,0.30),0_8px_30px_rgba(0,0,0,0.45)]",
            "transition-shadow duration-300",
          )}
        />

        {/* Top edge specular highlight */}
        <span
          aria-hidden
          className="pointer-events-none absolute inset-x-3 top-px h-px bg-gradient-to-r from-transparent via-white/45 to-transparent"
        />

        <input
          ref={ref}
          {...rest}
          className={cn(
            "relative z-10 w-full bg-transparent",
            "px-5 py-3 text-sm sm:text-base font-normal tracking-normal",
            "text-white placeholder:text-white/35",
            "outline-none focus:outline-none",
          )}
        />
      </motion.div>
    );
  },
);
