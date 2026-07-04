// 8-point spacing grid — Document 01 §Spacing System, Document 12 §Spacing.
// Never invent a spacing value outside this scale.
export const spacing = {
  1: 4,
  2: 8,
  3: 12,
  4: 16,
  5: 24,
  6: 32,
  7: 40,
  8: 48,
  9: 64,
  10: 80,
  11: 96,
} as const;

/** Component-level spacing rules from Document 02 §Component Spacing. */
export const componentSpacing = {
  internal: spacing[5], // 24px
  cardPadding: spacing[6], // 32px
  sectionGap: spacing[9], // 64px
  screenMarginDesktop: spacing[8], // 48px
  screenMarginTablet: spacing[6], // 32px
  screenMarginMobile: 20,
} as const;
