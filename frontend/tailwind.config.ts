import type { Config } from "tailwindcss";

// ShiftIQ design tokens — Documents 01 (Art Direction) and 12 (UI Kit).
// Every color, radius, shadow, and spacing value used in the app should
// come from here. Never hardcode hex values or px values in components.
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Backgrounds — crisp white primary background (per direct feedback,
        // overriding Doc 01's "never pure white" guidance), pale sage-cream
        // reserved for section breaks only, matching the Granola reference.
        bg: "#FFFFFF",
        surface: "#FFFFFF", // cards differentiated by hairline border + soft shadow, not tint
        "surface-hover": "#F2F2EC", // sunken section band / hover state
        border: "#EAEBE5",

        // Text
        text: "#26231F", // Warm Charcoal — replaces pure black
        muted: "#756F68", // Stone — descriptions, metadata, labels

        // Accents
        accent: {
          DEFAULT: "#647632", // Deep Rich Olive — primary buttons, links, active nav, progress
          dark: "#4F5E27",
          light: "#EBEEE3",
        },
        lavender: {
          DEFAULT: "#8A80C4", // Dusty Lavender — reserved for Insights / Future Check only
          light: "#EBE8F5",
        },
        success: {
          DEFAULT: "#7A9772", // Muted Moss
          light: "#E7EEE4",
        },
        warning: {
          DEFAULT: "#C8A15B", // Ochre
          light: "#F5EBD8",
        },
        danger: {
          DEFAULT: "#B9655C", // Clay
          light: "#F5E3E1",
        },
        "nav-selected": "#EBEEE3",

        // Neutral scale — ~90% of the interface should be composed of these.
        neutral: {
          50: "#FBF9F5",
          100: "#F2EEE7",
          200: "#E8E2D9",
          300: "#D5D0C7",
          400: "#B7B1A8",
          500: "#918B84",
          600: "#756F68",
          700: "#58534E",
          800: "#3B3834",
          900: "#26231F",
          950: "#171614",
        },
      },
      borderRadius: {
        xs: "8px",
        sm: "12px",
        md: "16px",
        lg: "24px",
        xl: "32px",
        hero: "40px",
        pill: "999px",
      },
      boxShadow: {
        // One elevation system — extremely soft, never dramatic.
        1: "0 1px 3px rgba(38, 35, 31, 0.05)",
        2: "0 10px 30px rgba(38, 35, 31, 0.08)",
        3: "0 16px 40px rgba(38, 35, 31, 0.10)",
        // Back-compat aliases so pages not yet in this redesign pass
        // (Shifts/Expenses/Jobs/Goals/Simulation) don't lose their shadows.
        soft: "0 1px 3px rgba(38, 35, 31, 0.05)",
        card: "0 10px 30px rgba(38, 35, 31, 0.08)",
        lift: "0 16px 40px rgba(38, 35, 31, 0.10)",
      },
      spacing: {
        13: "52px", // occasional editorial spacing between the 48/64 steps
      },
      maxWidth: {
        content: "1280px",
        reading: "680px",
        dialog: "720px",
        form: "640px",
        empty: "520px",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        serif: ["var(--font-newsreader)", "Georgia", "serif"],
      },
      fontSize: {
        hero: ["64px", { lineHeight: "1.05", letterSpacing: "-0.02em" }],
        "page-title": ["48px", { lineHeight: "1.1", letterSpacing: "-0.02em" }],
        section: ["32px", { lineHeight: "1.15" }],
        "card-heading": ["24px", { lineHeight: "1.2" }],
        "body-lg": ["18px", { lineHeight: "1.6" }],
        caption: ["14px", { lineHeight: "1.4" }],
        metadata: ["12px", { lineHeight: "1.3" }],
      },
      transitionDuration: {
        default: "200ms",
        complex: "300ms",
        page: "250ms",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "scale-in": {
          from: { opacity: "0", transform: "scale(0.98)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
        "slide-up": {
          from: { transform: "translateY(100%)" },
          to: { transform: "translateY(0)" },
        },
        "slide-in-right": {
          from: { transform: "translateX(100%)" },
          to: { transform: "translateX(0)" },
        },
        // Very subtle ambient drift for the Today Hero background (Doc 05
        // revision: ambient motion, ombre by time of day — never flashy).
        sunrise: {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
      },
      animation: {
        "fade-up": "fade-up 200ms ease-out",
        "fade-in": "fade-in 200ms ease-out",
        "scale-in": "scale-in 200ms ease-out",
        "slide-up": "slide-up 250ms ease-out",
        "slide-in-right": "slide-in-right 250ms ease-out",
        sunrise: "sunrise 24s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
