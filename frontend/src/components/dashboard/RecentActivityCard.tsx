import Link from "next/link";
import { LucideIcon, CalendarClock, Receipt } from "lucide-react";
import { BentoCard } from "./BentoCard";

export interface ActivityItem {
  id: string;
  icon: LucideIcon;
  label: string;
  dateLabel: string;
  amount: number;
  tone: "positive" | "negative";
}

// Sign is driven by `tone`, not the raw amount — expense amounts come back
// from the API as positive magnitudes, so a "negative" tone still needs an
// explicit minus sign here rather than trusting Math.sign(amount).
function money(n: number, tone: ActivityItem["tone"]): string {
  return `${tone === "positive" ? "+" : "-"}$${Math.abs(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

interface RecentActivityCardProps {
  items: ActivityItem[];
  className?: string;
}

export function RecentActivityCard({ items, className }: RecentActivityCardProps) {
  return (
    <BentoCard className={className}>
      <div className="between">
        <p className="card-title">Recent activity</p>
        <Link href="/shifts" className="text-btn">
          View all
        </Link>
      </div>

      {items.length > 0 ? (
        <div className="activity-list">
          {items.map((item) => {
            const Icon = item.icon;
            return (
              <div className="activity-row" key={item.id}>
                <div className="flex items-center gap-3">
                  <Icon size={16} aria-hidden="true" className="shrink-0 text-[var(--muted)]" />
                  <div>
                    <strong>{item.label}</strong>
                    <p className="muted-small">{item.dateLabel}</p>
                  </div>
                </div>
                <span className={item.tone === "positive" ? "positive" : "negative"}>
                  {money(item.amount, item.tone)}
                </span>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="muted">Nothing logged yet — add a shift or expense to get started.</p>
      )}
    </BentoCard>
  );
}

export const activityIcons = { shift: CalendarClock, expense: Receipt };
