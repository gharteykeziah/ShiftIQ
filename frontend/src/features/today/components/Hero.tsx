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
  /** Time-of-day tone for the ambient glow behind the card stack. */
  timeOfDay: "morning" | "afternoon" | "evening";

  // Front card — Today's recommendation ("Next Best Move"). This is the
  // same recommendation shown in the sticky Decision Bar below; the Hero
  // card is what's visible before that bar takes over on scroll.
  recommendationTitle: string;
  recommendationOutcome?: string;
  recommendationImpact: string;
  recommendationHref: string;

  // Back cards — real product data, cropped and quieted so they read as
  // "there's more here" rather than competing with the front card.
  goalName: string;
  goalCurrent: string;
  goalTarget: string;
  weeklyLabel: string;
  weeklyAmount: string;
}

const glowTone: Record<HeroProps["timeOfDay"], string> = {
  // Extremely low-opacity, warm-paper-family glow — implies soft studio
  // light behind the card stack rather than a decorative gradient panel.
  morning: "bg-[#F6C97A]",
  afternoon: "bg-[#E8B98F]",
  evening: "bg-[#C9A6C7]",
};

/**
 * Document 05 §Hero, redirected per Design Direction A + B + D: no
 * illustration, no SVG artwork. The right side is composed from real
 * product content — a layered stack of the day's actual cards — treated
 * with editorial overlap and material depth instead of decoration.
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
  recommendationTitle,
  recommendationOutcome,
  recommendationImpact,
  recommendationHref,
  goalName,
  goalCurrent,
  goalTarget,
  weeklyLabel,
  weeklyAmount,
}: HeroProps) {
  return (
    <section className="animate-fade-up relative py-4 md:py-8">
      <div className="grid grid-cols-1 gap-12 lg:grid-cols-12 lg:items-start lg:gap-0">
        {/* Editorial text block. */}
        <div className="lg:col-span-7 lg:pr-6">
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

        {/* Layered stack — Concept B. All three cards occupy the exact same
            box (via inset-0 in a fixed-size relative frame) so the back
            cards peek out from consistent, controlled corners instead of
            drifting to arbitrary positions. The overlap with the headline
            column (Concept A) is deliberately shallow and sits low enough
            to land in the whitespace below the headline's second line
            rather than cutting through the large serif glyphs themselves —
            a magazine layout overlaps into negative space, never into the
            letters. */}
        <div className="relative mx-auto w-full max-w-[360px] lg:col-span-5 lg:col-start-8 lg:mx-0 lg:-ml-8 lg:mt-28">
          {/* Soft ambient glow — implied lighting, not a decorative panel:
              heavily blurred, very low opacity, sits behind the frame. */}
          <div
            className={`absolute -inset-8 -z-10 rounded-full opacity-[0.08] blur-3xl ${glowTone[timeOfDay]}`}
            aria-hidden="true"
          />

          <div className="relative h-[248px]">
            {/* Back card — Expected this week. Furthest back, peeks top-right. */}
            <div
              className="absolute inset-0 translate-x-4 -translate-y-3 rotate-[4deg] rounded-lg border border-border bg-surface-hover/80 p-6 opacity-50 shadow-1"
              aria-hidden="true"
            >
              <p className="text-caption text-muted">{weeklyLabel}</p>
              <p className="mt-1 font-serif text-2xl font-medium text-muted">{weeklyAmount}</p>
            </div>

            {/* Back card — Current goal. Peeks bottom-left, less muted. */}
            <div
              className="absolute inset-0 -translate-x-3 translate-y-4 rotate-[-3deg] rounded-lg border border-border bg-surface p-6 opacity-70 shadow-1"
              aria-hidden="true"
            >
              <p className="text-caption text-muted">{goalName}</p>
              <p className="mt-1 font-serif text-2xl font-medium text-text/80">
                {goalCurrent} <span className="text-sm text-muted">/ {goalTarget}</span>
              </p>
            </div>

            {/* Front card — Material Surface treatment: hairline border,
                two-layer shadow, faint internal top-light, one thin olive
                edge tab instead of a full-perimeter accent. */}
            <Link
              href={recommendationHref}
              className="group absolute inset-0 z-20 flex flex-col justify-center overflow-hidden rounded-lg border border-border bg-surface p-7 shadow-elevated transition-transform duration-200 hover:-translate-y-0.5"
            >
              <span
                className="pointer-events-none absolute inset-0 bg-gradient-to-b from-white/70 via-transparent to-transparent"
                aria-hidden="true"
              />
              <span className="absolute inset-y-4 left-0 w-[3px] rounded-full bg-accent" aria-hidden="true" />
              <div className="relative pl-2">
                <p className="text-metadata font-semibold uppercase tracking-wide text-accent">Next best move</p>
                <p className="mt-2 font-serif text-card-heading font-medium leading-snug text-text">
                  {recommendationTitle}
                </p>
                {recommendationOutcome && (
                  <p className="mt-1 text-sm font-medium text-accent-dark">{recommendationOutcome}</p>
                )}
                <p className="mt-3 text-sm text-muted">{recommendationImpact}</p>
                <p className="mt-4 text-sm font-medium text-text underline-offset-4 group-hover:underline">View →</p>
              </div>
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
