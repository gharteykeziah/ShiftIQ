import Link from "next/link";

interface OpportunitySuggestion {
  day: string;
  hours: number;
  pay: string;
  impact: string;
}

interface OpportunityCardProps {
  suggestion: OpportunitySuggestion | null;
}

/**
 * Document 02/05/06/12 §Opportunity Card: exactly one recommendation, never
 * a list of shifts. Derived from the user's own shift history — an honest
 * empty state replaces a fabricated suggestion when there isn't enough data.
 */
export function OpportunityCard({ suggestion }: OpportunityCardProps) {
  return (
    <div className="hover-lift rounded-lg border border-border bg-surface p-8">
      <p className="text-sm font-medium text-muted">Today&apos;s opportunity</p>

      {suggestion ? (
        <>
          <p className="mt-2 font-serif text-card-heading font-medium text-text">{suggestion.day}</p>
          <p className="mt-1 text-sm font-medium text-accent-dark">
            {suggestion.hours} hours · {suggestion.pay}
          </p>
          <p className="mt-3 text-sm text-muted">{suggestion.impact}</p>
          <Link
            href="/shifts"
            className="mt-5 inline-flex h-11 items-center justify-center rounded-md bg-accent px-5 text-sm font-medium text-white transition-colors duration-200 hover:bg-accent-dark"
          >
            Accept shift
          </Link>
        </>
      ) : (
        <>
          <p className="mt-2 font-serif text-card-heading font-medium text-text">No pattern yet</p>
          <p className="mt-3 text-sm text-muted">
            Log a few more shifts and we&apos;ll start spotting your best opportunities.
          </p>
          <Link href="/shifts" className="mt-5 inline-block text-sm font-medium text-accent hover:underline">
            Add a shift →
          </Link>
        </>
      )}
    </div>
  );
}
