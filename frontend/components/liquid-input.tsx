"use client";

import { motion } from "framer-motion";
import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type LiquidInputProps = InputHTMLAttributes<HTMLInputElement> & {
  shake?: boolean;
};

export const LiquidInput = forwardRef<HTMLInputElement, LiquidInputProps>(
  function LiquidInput({ className, shake, ...rest }, ref) {
    return (
      <motion.div
        animate={shake ? { x: [0, -8, 8, -6, 6, -3, 3, 0] } : { x: 0 }}
        transition={{ duration: 0.5 }}
        className={cn(
          "relative flex w-full items-center rounded-full",
          "bg-[color-mix(in_oklab,white_5%,transparent)] backdrop-blur-xl",
          "border border-white/10 hover:border-white/20 focus-within:border-cyan-300/50",
          "shadow-[inset_0_1px_0_rgba(255,255,255,0.18),inset_0_-1px_0_rgba(0,0,0,0.5),0_8px_30px_rgba(0,0,0,0.45)]",
          "transition-colors",
          className,
        )}
      >
        <input
          ref={ref}
          {...rest}
          className={cn(
            "w-full bg-transparent px-5 py-3 text-base font-normal tracking-normal",
            "text-white placeholder:text-white/35",
            "outline-none focus:outline-none",
          )}
        />
        {/* refractive top-edge highlight */}
        <span
          aria-hidden
          className="pointer-events-none absolute inset-x-3 top-px h-px bg-gradient-to-r from-transparent via-white/40 to-transparent"
        />
      </motion.div>
    );
  },
);
