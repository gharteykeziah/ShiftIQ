// Motion tokens — Document 01 §Motion Language, Document 02 §Animation Rules,
// Document 12 §Motion Library.
//
// Implementation note: this app doesn't have network access to install
// Framer Motion in this pass, so motion is implemented with Tailwind's
// generated CSS animation utilities (see tailwind.config.ts: animate-fade-up,
// animate-fade-in, animate-scale-in, animate-slide-up, animate-slide-in-right)
// plus the `hover-lift` utility in globals.css. These constants exist so any
// JS-driven timing (stagger delays, setTimeout-based sequencing) stays in
// sync with those CSS values instead of using magic numbers.
export const duration = {
  default: 200,
  complex: 300,
  page: 250,
  mobile: 175, // Doc 07: mobile animations run slightly faster (150-200ms)
} as const;

export const stagger = {
  listItem: 40, // ms between each item in a staggered list
} as const;

export const hover = {
  liftPx: 4,
  scale: 1.02,
} as const;

export const easing = {
  standard: "ease-out",
} as const;

/** Never: bounce, overshoot, or flashy transitions (Doc 01/02/12). */
