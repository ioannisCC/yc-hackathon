"use client";

import { motion, type HTMLMotionProps } from "framer-motion";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "ghost";
type Size = "default" | "lg" | "xl";

type LiquidButtonProps = Omit<HTMLMotionProps<"button">, "children"> & {
  variant?: Variant;
  size?: Size;
  children: ReactNode;
};

/** Refractive liquid-glass button. Backdrop is warped by the SVG turbulence
 *  filter mounted once in the root layout (#liquid-glass). The shadow stack
 *  is the load-bearing aesthetic — multi-inset edges + outer cyan glow on
 *  primary variant. */
export function LiquidButton({
  variant = "primary",
  size = "default",
  className,
  children,
  ...rest
}: LiquidButtonProps) {
  const sizes: Record<Size, string> = {
    default: "px-6 py-3 text-sm",
    lg:      "px-8 py-3.5 text-base",
    xl:      "px-10 py-4 text-lg",
  };

  return (
    <motion.button
      whileTap={{ scale: 0.97 }}
      whileHover={{ scale: 1.02 }}
      transition={{ type: "spring", stiffness: 420, damping: 22 }}
      className={cn(
        "group relative isolate inline-flex select-none items-center justify-center gap-2 rounded-full",
        "font-medium tracking-wide text-white outline-none",
        "disabled:cursor-not-allowed disabled:opacity-50",
        sizes[size],
        className,
      )}
      {...rest}
    >
      {/* The lens — empty layer with backdrop-filter so Chrome refracts the
          background BEHIND the button, not the button text. */}
      <span
        aria-hidden
        className={cn(
          "absolute inset-0 -z-10 rounded-full",
          "backdrop-blur-xl",
          variant === "primary"
            ? "bg-[color-mix(in_oklab,#22d3ee_22%,black_78%)]"
            : "bg-white/[0.06]",
        )}
        style={{ backdropFilter: "url(#liquid-glass) blur(12px) saturate(140%)" }}
      />

      {/* Multi-layer inset shadows + edge highlights + cyan halo on primary. */}
      <span
        aria-hidden
        className={cn(
          "absolute inset-0 rounded-full",
          variant === "primary"
            ? "shadow-[inset_0_1px_0_rgba(255,255,255,0.30),inset_0_-1px_0_rgba(0,0,0,0.45),inset_0_0_0_1px_rgba(34,211,238,0.45),0_0_28px_rgba(34,211,238,0.45),0_10px_30px_rgba(0,0,0,0.55)]"
            : "shadow-[inset_0_1px_0_rgba(255,255,255,0.18),inset_0_-1px_0_rgba(0,0,0,0.45),inset_0_0_0_1px_rgba(255,255,255,0.10),0_6px_24px_rgba(0,0,0,0.45)]",
        )}
      />

      {/* Top-edge specular highlight */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-3 top-px h-px bg-gradient-to-r from-transparent via-white/55 to-transparent"
      />

      <span className="relative z-10 flex items-center gap-2">{children}</span>
    </motion.button>
  );
}
