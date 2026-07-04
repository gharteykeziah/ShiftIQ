import Link from "next/link";
import { CalendarPlus, ArrowRight } from "lucide-react";
import { BentoCard, IconBadge } from "./BentoCard";

function money(n: number): string {
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

interface OpportunitySuggestion {
  day: string;
  hours: number;
  pay: number;
  note: string;
}

interface OpportunityCardProps {
  suggestion: OpportunitySuggestion | null;
  className?: string;
}

/**
 * "Today's opportunity" — a pattern-based suggestion derived from the
 * user's own shift history (best-earning weekday), not a fake shift
 * marketplace. When there isn't enough history yet, shows an honest
 * empty state instead of inventing a shift.
 */
export function OpportunityCard({ suggestion, className }: OpportunityCardProps) {
  return (
    <BentoCard className={className}>
      <IconBadge className="purple">
        <CalendarPlus size={20} aria-hidden="true" />
      </IconBadge>
      <p className="card-title">Today&apos;s opportunity</p>

      {suggestion ? (
        <>
          <h2>{suggestion.day} shift</h2>
          <p className="highlight">
            {suggestion.hours}h · +{money(suggestion.pay)}
          </p>
          <p className="muted">{suggestion.note}</p>
          <div className="card-actions">
            <Link href="/shifts" className="purple-btn">
              Add this shift
            </Link>
            <Link href="/shifts" className="text-btn">
              View details <ArrowRight size={16} aria-hidden="true" />
            </Link>
          </div>
        </>
      ) : (
        <>
          <h2>No pattern yet</h2>
          <p className="muted">
            Log a few more shifts and I&apos;ll start spotting your best opportunities to pick up
            extra hours.
          </p>
          <Link href="/shifts" className="text-btn">
            Add a shift <ArrowRight size={16} aria-hidden="true" />
          </Link>
        </>
      )}
    </BentoCard>
  );
}
