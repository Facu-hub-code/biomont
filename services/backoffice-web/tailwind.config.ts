import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        biomont: {
          primary: "#0f4c5c",
          accent: "#e36414",
        },
      },
    },
  },
  plugins: [],
};

export default config;
