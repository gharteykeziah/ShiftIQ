// ShiftIQ color tokens — Document 01 (Art Direction) & Document 12 (UI Kit).
// This is the single JS-readable source of truth for colors used outside
// Tailwind class names (Recharts fills, canvas/inline-style calculations,
// dynamic style objects). Tailwind's own token copies live in
// tailwind.config.ts — keep the two in sync if either changes.
export const colors = {
  bg: "#F6F3EC", // Warm Paper
  surface: "#FFFCF8", // Soft Ivory
  surfaceHover: "#F2EEE7",
  border: "#E7E1D8",

  text: "#26231F", // Warm Charcoal
  muted: "#756F68", // Stone

  accent: "#647632", // Deep Rich Olive — primary actions, active nav, progress
  accentDark: "#4F5E27",
  accentLight: "#EBEEE3",

  // Reserved exclusively for Insights / Future Check / pattern recognition.
  lavender: "#8A80C4",
  lavenderLight: "#EBE8F5",

  success: "#7A9772", // Muted Moss
  successLight: "#E7EEE4",
  warning: "#C8A15B", // Ochre
  warningLight: "#F5EBD8",
  danger: "#B9655C", // Clay
  dangerLight: "#F5E3E1",

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
} as const;

/** Ordered fill sequence for the rare chart that still needs one (Doc 12: line/area/simple bar only, never pie/donut/radar/gauge). */
export const chartFillOrder = [colors.accent, colors.lavender, colors.warning, colors.success] as const;
