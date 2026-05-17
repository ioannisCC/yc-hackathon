import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Cyan glow — matches the lamp ambient & active-step inner glow
        glow: {
          DEFAULT: "#22d3ee",
          dim: "rgba(34, 211, 238, 0.18)",
          line: "rgba(34, 211, 238, 0.35)",
        },
        glass: {
          surface: "rgba(255, 255, 255, 0.04)",
          edge: "rgba(255, 255, 255, 0.08)",
          highlight: "rgba(255, 255, 255, 0.16)",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
      },
      transitionTimingFunction: {
        "out-expo": "cubic-bezier(0.22, 1, 0.36, 1)",
      },
      animation: {
        "pulse-glow": "pulseGlow 2.4s ease-in-out infinite",
      },
      keyframes: {
        pulseGlow: {
          "0%, 100%": { opacity: "0.7", filter: "blur(20px)" },
          "50%":      { opacity: "1.0", filter: "blur(28px)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
