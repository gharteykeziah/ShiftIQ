// Typography scale — Document 01 §Typography. Newsreader for headings only
// (never body text), Inter for everything else. Never go below 12px anywhere,
// never below 16px for body copy.
export const fontScale = {
  hero: 64,
  pageTitle: 48,
  section: 32,
  cardHeading: 24,
  bodyLarge: 18,
  body: 16,
  caption: 14,
  metadata: 12,
} as const;

export const fontWeight = {
  hero: 700,
  title: 600,
  body: 400,
  button: 500,
  numbers: 600,
} as const;

/** Responsive Hero sizes — Document 04 §Responsive Typography. */
export const heroResponsive = {
  desktop: 64,
  tablet: 52,
  mobile: 40,
} as const;
