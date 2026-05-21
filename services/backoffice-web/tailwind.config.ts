import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      colors: {
        biomont: {
          primary: "#0f4c5c",
          accent: "#e36414",
        },
      },
      boxShadow: {
        soft:
          "0 4px 24px -6px rgba(15, 76, 92, 0.07), 0 12px 48px -16px rgba(15, 23, 42, 0.06)",
        lift: "0 8px 30px -10px rgba(15, 76, 92, 0.12), 0 4px 12px -6px rgba(0, 0, 0, 0.05)",
        glow: "0 0 0 1px rgba(255,255,255,0.65) inset, 0 18px 50px -24px rgba(15, 76, 92, 0.35)",
      },
      transitionDuration: {
        250: "250ms",
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        fadeUp: "fadeUp 0.35s ease-out forwards",
      },
    },
  },
  plugins: [],
};

export default config;
