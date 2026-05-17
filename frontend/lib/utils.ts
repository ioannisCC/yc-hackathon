import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function formatPhone(e164: string): string {
  // +12527654517 → +1 (252) 765-4517
  const m = e164.match(/^\+(\d)(\d{3})(\d{3})(\d{4})$/);
  if (!m) return e164;
  return `+${m[1]} (${m[2]}) ${m[3]}-${m[4]}`;
}
