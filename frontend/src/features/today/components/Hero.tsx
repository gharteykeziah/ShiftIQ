import Link from "next/link";

interface HeroProps {
  greeting: string;
  headline: string;
  description: string;
  contextLine?: string;
  primaryLabel: string;
  primaryHref: string;
  secondaryLabel?: string;
  secondaryHref?: string;
  /** Time-of-day tone for the ambient background — Document 05 revision. */
  timeOfDay: "morning" | "afternoon" | "evening";
}

const timeGradient: Record<HeroProps["timeOfDay"], string> = {
  // All extremely low-contrast, warm-paper-family tones — ambient, not decorative.
  morning: "from-[#FBF3E1] via-[#F6F3EC] to-[#F2EEE7]",
  afternoon: "from-[#F6F0E4] via-[#F6F3EC] to-[#EFEBE2]",
  evening: "from-[#EFE7E2] via-[#F1EBE5] to-[#F6F3EC]",
};

/**
 * Document 05 §Hero: the emotional center of the app. One headline, one
 * supporting paragraph, max two buttons. Never charts, never metrics inside
 * it. The gradient is a very subtle, slow-drifting time-of-day tone rather
 * than a photo or illustration — ambient polish, not decoration.
 */
export function Hero({
  greeting,
  headline,
  description,
  contextLine,
  primaryLabel,
  primaryHref,
  secondaryLabel,
  secondaryHref,
  timeOfDay,
}: HeroProps) {
  return (
    <section
      className={`animate-fade-up relative flex min-h-[220px] items-center overflow-hidden rounded-hero bg-gradient-to-br bg-[length:200%_200%] px-6 py-8 animate-sunrise md:min-h-[340px] md:px-12 md:py-12 ${timeGradient[timeOfDay]}`}
    >
      <div className="max-w-2xl">
        <p className="text-body-lg text-muted">{greeting}</p>
        <h1 className="mt-2 font-serif text-[40px] font-normal leading-[1.1] tracking-tight text-text md:text-hero">
          {headline}
        </h1>
        <p className="mt-4 max-w-xl text-body-lg text-muted">{description}</p>
        {contextLine && <p className="mt-3 text-sm font-medium text-accent-dark">{contextLine}</p>}

        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href={primaryHref}
            className="inline-flex h-12 items-center justify-center rounded-md bg-accent px-6 text-sm font-medium text-white transition-colors duration-200 hover:bg-accent-dark"
          >
            {primaryLabel}
          </Link>
          {secondaryLabel && secondaryHref && (
            <Link
              href={secondaryHref}
              className="inline-flex h-12 items-center justify-center rounded-md border border-border bg-transparent px-6 text-sm font-medium text-text transition-colors duration-200 hover:bg-surface-hover"
            >
              {secondaryLabel}
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}
