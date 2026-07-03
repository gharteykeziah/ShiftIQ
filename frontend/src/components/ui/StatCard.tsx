import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string;
  icon?: LucideIcon;
  trend?: "up" | "down" | "neutral";
  trendLabel?: string;
  className?: string;
}

/** Dashboard summary card — one per StateSummary field (balance, weekly income, etc). */
export function StatCard({ label, value, icon: Icon, trend, trendLabel, className }: StatCardProps) {
  const trendColor = trend === "up" ? "text-accent" : trend === "down" ? "text-danger" : "text-muted";

  return (
    <div className={cn("rounded-3xl bg-surface p-5 shadow-card", className)}>
      <div className="mb-3 flex items-center justify-between">
        <span className="text-sm font-medium text-muted">{label}</span>
        {Icon && (
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-accent-light">
            <Icon className="h-4 w-4 text-accent" aria-hidden="true" />
          </span>
        )}
      </div>
      <p className="text-2xl font-bold text-text">{value}</p>
      {trendLabel && <p className={cn("mt-1 text-xs font-medium", trendColor)}>{trendLabel}</p>}
    </div>
  );
}
