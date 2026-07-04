import Link from "next/link";
import { Target, ArrowRight } from "lucide-react";
import { BentoCard, IconBadge } from "./BentoCard";

function money(n: number): string {
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

interface GoalProgressCardProps {
  title: string;
  saved: number;
  target: number;
  timeLabel: string;
  moveText?: string;
  href: string;
  className?: string;
}

/** Compact goal card for the dashboard bento grid. */
export function GoalProgressCard({
  title,
  saved,
  target,
  timeLabel,
  moveText,
  href,
  className,
}: GoalProgressCardProps) {
  const pct = target > 0 ? Math.min(100, Math.max(0, (saved / target) * 100)) : 0;

  return (
    <BentoCard className={className}>
      <IconBadge className="green">
        <Target size={20} aria-hidden="true" />
      </IconBadge>
      <p className="card-title">{title}</p>
      <h2>
        {money(saved)} <span className="muted-small">/ {money(target)}</span>
      </h2>

      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${Math.max(4, pct)}%` }} />
      </div>
      <div className="between">
        <p>{timeLabel}</p>
        <p>{Math.round(pct)}%</p>
      </div>

      {moveText && (
        <Link href={href} className="soft-callout">
          {moveText}
          <ArrowRight size={16} aria-hidden="true" />
        </Link>
      )}
    </BentoCard>
  );
}
