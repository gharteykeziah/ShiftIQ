import Link from "next/link";
import { Sparkles } from "lucide-react";
import { BentoCard, IconBadge } from "./BentoCard";

interface InsightCardProps {
  heading: string;
  body: string;
  ctaLabel?: string;
  ctaHref?: string;
  className?: string;
}

/** "ShiftIQ noticed something" — a single plain-English insight. */
export function InsightCard({ heading, body, ctaLabel, ctaHref, className }: InsightCardProps) {
  return (
    <BentoCard className={className}>
      <IconBadge className="purple">
        <Sparkles size={20} aria-hidden="true" />
      </IconBadge>
      <p className="card-title">ShiftIQ noticed something</p>
      <h3>{heading}</h3>
      <p className="muted">{body}</p>
      {ctaLabel && ctaHref && (
        <Link href={ctaHref} className="purple-soft-btn">
          {ctaLabel}
        </Link>
      )}
    </BentoCard>
  );
}
