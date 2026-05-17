"use client";

import { motion, type HTMLMotionProps } from "framer-motion";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Size = "sm" | "md" | "lg";
type GlowIntensity = "none" | "soft" | "active";

type GlassCardProps = Omit<HTMLMotionProps<"div">, "children"> & {
  size?: Size;
  glow?: GlowIntensity;
  children: ReactNode;
};

const SIZE_PADDING: Record<Size, string> = {
  sm: "p-3 sm:p-4",
  md: "p-4 sm:p-5",
  lg: "p-5 sm:p-6",
};

const GLOW_SHADOW: Record<GlowIntensity, string> = {
  none:
    "shadow-[inset_0_1px_0_rgba(255,255,255,0.08),inset_0_-1px_0_rgba(0,0,0,0.55),inset_0_0_0_1px_rgba(255,255,255,0.06),0_8px_28px_rgba(0,0,0,0.40)]",
  soft:
    "shadow-[inset_0_1px_0_rgba(255,255,255,0.10),inset_0_-1px_0_rgba(0,0,0,0.55),inset_0_0_0_1px_rgba(255,255,255,0.07),0_8px_28px_rgba(0,0,0,0.40),0_0_24px_rgba(34,211,238,0.08)]",
  active:
    "shadow-[inset_0_1px_0_rgba(255,255,255,0.12),inset_0_0_0_1px_rgba(34,211,238,0.45),inset_0_0_36px_rgba(34,211,238,0.18),0_0_48px_rgba(34,211,238,0.22),0_8px_28px_rgba(0,0,0,0.40)]",
};

export function GlassCard({
  size = "md",
  glow = "none",
  className,
  children,
  ...rest
}: GlassCardProps) {
  return (
    <motion.div
      className={cn(
        "relative isolate rounded-2xl bg-white/[0.025] backdrop-blur-xl",
        "transition-shadow duration-500",
        SIZE_PADDING[size],
        GLOW_SHADOW[glow],
        className,
      )}
      {...rest}
    >
      {/* Refractive top edge */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-4 top-px h-px bg-gradient-to-r from-transparent via-white/20 to-transparent"
      />
      {children}
    </motion.div>
  );
}
