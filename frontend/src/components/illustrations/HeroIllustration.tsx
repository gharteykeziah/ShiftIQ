interface HeroIllustrationProps {
  className?: string;
}

/**
 * Simple original illustration for the onboarding flow, in the spirit of
 * the Truebill/Rocket Money reference (soft pastel blob + a friendly card
 * with a completed checkmark) but hand-drawn in SVG rather than a stock
 * asset, so there's no image file to manage.
 */
export function HeroIllustration({ className }: HeroIllustrationProps) {
  return (
    <svg
      viewBox="0 0 400 320"
      className={className}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <circle cx="200" cy="160" r="150" fill="#D4EDDA" />
      <circle cx="90" cy="86" r="22" fill="#2563EB" opacity="0.85" />
      <circle cx="322" cy="92" r="12" fill="#C0392B" opacity="0.45" />
      <circle cx="316" cy="232" r="16" fill="#1B6B3A" opacity="0.5" />
      <rect x="105" y="115" width="190" height="130" rx="26" fill="#FFFFFF" />
      <rect x="128" y="143" width="144" height="14" rx="7" fill="#E6F2EB" />
      <rect x="128" y="169" width="104" height="14" rx="7" fill="#E6F2EB" />
      <circle cx="236" cy="210" r="20" fill="#1B6B3A" />
      <path
        d="M228 210l6 6 12-12"
        stroke="white"
        strokeWidth="3.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
