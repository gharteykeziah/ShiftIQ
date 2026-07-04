import Link from "next/link";
import { CalendarDays, ArrowRight } from "lucide-react";
import { BentoCard, IconBadge } from "./BentoCard";
import { hoursBetween } from "@/lib/utils";
import type { ShiftOut } from "@/lib/types";

function money(n: number): string {
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatTime12h(time: string): string {
  const [hStr, mStr] = time.split(":");
  const h = Number(hStr);
  const m = Number(mStr);
  const ampm = h < 12 ? "AM" : "PM";
  const h12 = h % 12 || 12;
  return `${h12}:${String(m).padStart(2, "0")} ${ampm}`;
}

interface TodayPlanCardProps {
  shifts: ShiftOut[];
  className?: string;
}

export function TodayPlanCard({ shifts, className }: TodayPlanCardProps) {
  return (
    <BentoCard className={className}>
      <IconBadge className="amber">
        <CalendarDays size={20} aria-hidden="true" />
      </IconBadge>
      <p className="card-title">Today&apos;s plan</p>

      {shifts.length > 0 ? (
        <div className="plan-list">
          {shifts.map((s) => {
            const hours = hoursBetween(s.start_time, s.end_time);
            const pay = Math.round(hours * s.hourly_rate);
            return (
              <div className="plan-row" key={s.id}>
                <div>
                  <p className="muted-small">
                    {formatTime12h(s.start_time)} – {formatTime12h(s.end_time)}
                  </p>
                  <strong>{s.title}</strong>
                </div>
                <span>{hours}h</span>
                <strong className="positive">+{money(pay)}</strong>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="muted">Nothing on the calendar today. Enjoy the downtime.</p>
      )}

      <Link href="/shifts" className="text-btn">
        View full schedule <ArrowRight size={16} aria-hidden="true" />
      </Link>
    </BentoCard>
  );
}
