import type { Config } from "tailwindcss";

// Colors translated from theme.py's light palette, plus a couple of derived
// hover/dark shades for interactive states. Kept as flat hex values for now;
// if/when we add a dark mode toggle, these become CSS variables instead.
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#F0F4F1",
        surface: "#FFFFFF",
        "surface-hover": "#F5F8F6",
        border: "#D8E4DC",
        text: "#1A2E22",
        muted: "#7A9485",
        accent: {
          DEFAULT: "#1B6B3A",
          dark: "#155C30",
          light: "#D4EDDA",
        },
        blue: {
          DEFAULT: "#2563EB",
          dark: "#1D4ED8",
        },
        danger: {
          DEFAULT: "#C0392B",
          dark: "#A93226",
        },
        "nav-selected": "#E6F2EB",
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1.25rem",
        "3xl": "1.75rem",
      },
      boxShadow: {
        soft: "0 2px 10px -2px rgba(26, 46, 34, 0.08)",
        card: "0 4px 20px -4px rgba(26, 46, 34, 0.10)",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
