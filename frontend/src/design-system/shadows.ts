// Elevation system — Document 01 §Shadows, Document 12 §Design Tokens.
// One system, extremely soft. Never dramatic, never multiple shadows stacked.
export const shadow = {
  1: "0 1px 3px rgba(38, 35, 31, 0.05)", // cards
  2: "0 10px 30px rgba(38, 35, 31, 0.08)", // dialogs
  3: "0 16px 40px rgba(38, 35, 31, 0.10)", // dropdowns
} as const;
