import { LucideIcon } from "lucide-react";

export interface ActivityItem {
  id: string;
  icon: LucideIcon;
  label: string;
  dateLabel: string;
  amount: string;
  tone: "positive" | "negative" | "neutral";
}

const toneClass: Record<ActivityItem["tone"], string> = {
  positive: "text-success",
  negative: "text-danger",
  neutral: "text-muted",
};

/** Document 02/05/12 §Activity Feed: Apple Wallet inspired, reverse chronological, minimal. */
export function ActivityFeed({ items }: { items: ActivityItem[] }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-8">
      <p className="mb-5 text-sm font-medium text-muted">Recent activity</p>
      {items.length > 0 ? (
        <ul className="space-y-5">
          {items.map((item) => {
            const Icon = item.icon;
            return (
              <li key={item.id} className="flex items-center gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-bg text-muted">
                  <Icon size={16} strokeWidth={2} aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-text">{item.label}</p>
                  <p className="text-caption text-muted">{item.dateLabel}</p>
                </div>
                <span className={`shrink-0 text-sm font-medium ${toneClass[item.tone]}`}>{item.amount}</span>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-sm text-muted">Nothing logged yet — add a shift or expense to get started.</p>
      )}
    </div>
  );
}
