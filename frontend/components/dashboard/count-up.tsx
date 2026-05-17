"use client";

import { motion, useMotionValue, useTransform, animate } from "framer-motion";
import { useEffect } from "react";
import { cn } from "@/lib/utils";

/** Tweens a number from its previous value to the new one over `duration`s.
 *  Re-animates whenever the `value` prop changes. */
export function CountUp({
  value,
  duration = 0.8,
  className,
}: {
  value: number;
  duration?: number;
  className?: string;
}) {
  const motionValue = useMotionValue(value);
  const rendered = useTransform(motionValue, (v) => Math.round(v).toLocaleString());

  useEffect(() => {
    const controls = animate(motionValue, value, {
      duration,
      ease: [0.22, 1, 0.36, 1],
    });
    return () => controls.stop();
  }, [value, duration, motionValue]);

  return <motion.span className={cn("tabular-nums", className)}>{rendered}</motion.span>;
}
