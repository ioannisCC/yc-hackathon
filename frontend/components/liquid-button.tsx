"use client";

import { motion, type HTMLMotionProps } from "framer-motion";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "ghost";

type LiquidButtonProps = Omit<HTMLMotionProps<"button">, "children"> & {
  variant?: Variant;
  children: ReactNode;
};

export function LiquidButton({
  variant = "primary",
  className,
  children,
  ...rest
}: LiquidButtonProps) {
  const styles =
    variant === "primary"
      ? "bg-[color-mix(in_oklab,#22d3ee_22%,black_78%)] border-cyan-300/30 hover:border-cyan-300/55 hover:bg-[color-mix(in_oklab,#22d3ee_30%,black_70%)] shadow-[inset_0_1px_0_rgba(255,255,255,0.25),0_0_30px_rgba(34,211,238,0.35),0_10px_30px_rgba(0,0,0,0.5)]"
      : "bg-white/5 border-white/10 hover:bg-white/10 hover:border-white/20 shadow-[inset_0_1px_0_rgba(255,255,255,0.12),0_4px_18px_rgba(0,0,0,0.35)]";

  return (
    <motion.button
      whileTap={{ scale: 0.96 }}
      transition={{ type: "spring", stiffness: 420, damping: 18 }}
      className={cn(
        "relative inline-flex select-none items-center justify-center rounded-full",
        "px-6 py-3 text-sm font-medium tracking-wide text-white",
        "border backdrop-blur-xl transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-50",
        styles,
        className,
      )}
      {...rest}
    >
      <span className="relative z-10">{children}</span>
      {/* refractive top-edge highlight */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-3 top-px h-px bg-gradient-to-r from-transparent via-white/55 to-transparent"
      />
    </motion.button>
  );
}
