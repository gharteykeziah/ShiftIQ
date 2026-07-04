import Link from "next/link";
import { Sparkles } from "lucide-react";

interface InsightCardProps {
  body: string;
  ctaLabel?: string;
  ctaHref?: string;
}

/**
 * Insight Card — dark charcoal (same "black" as the selected Goals tile)
 * with the olive accent, matching the rest of the app instead of a
 * one-off lavender treatment. One insight only, max 70 words.
 */
export function InsightCard({ body, ctaLabel, ctaHref }: InsightCardProps) {
  return (
    <div className="hover-lift rounded-lg bg-text p-8">
      <div className="mb-3 flex items-center gap-2 text-accent">
        <Sparkles size={20} strokeWidth={2} aria-hidden="true" />
        <span className="text-sm font-medium">Things worth noticing</span>
      </div>
      <p className="font-serif text-card-heading font-medium leading-snug text-white">{body}</p>
      {ctaLabel && ctaHref && (
        <Link
          href={ctaHref}
          className="mt-5 inline-flex h-11 items-center justify-center rounded-md bg-accent px-5 text-sm font-medium text-white transition-colors duration-200 hover:bg-accent-dark"
        >
          {ctaLabel}
        </Link>
      )}
    </div>
  );
}
