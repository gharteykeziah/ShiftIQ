import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind classes safely — later classes win over earlier conflicting
 * ones (e.g. cn("p-2", condition && "p-4") resolves to just "p-4").
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Hours between two "HH:MM" 24h time strings, rounded to 1 decimal. */
export function hoursBetween(start: string, end: string): number {
  const [sh, sm] = start.split(":").map(Number);
  const [eh, em] = end.split(":").map(Number);
  const mins = eh * 60 + em - (sh * 60 + sm);
  return Math.round((mins / 60) * 10) / 10;
}

/** "HH:MM" 24h time string formatted as 12h with AM/PM, e.g. "09:00" -> "9:00 AM". */
export function formatTime12h(time: string): string {
  const [hStr, mStr] = time.split(":");
  const h = Number(hStr);
  const m = Number(mStr);
  const ampm = h < 12 ? "AM" : "PM";
  const h12 = h % 12 || 12;
  return `${h12}:${String(m).padStart(2, "0")} ${ampm}`;
}

/** Dollar amount with cents, e.g. 1234.5 -> "$1,234.50". */
export function money(n: number): string {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** Dollar amount rounded to the nearest whole dollar, e.g. 1234.5 -> "$1,235". */
export function moneyRounded(n: number): string {
  return `$${Math.round(n).toLocaleString()}`;
}

/** First two letters of an email, upper-cased, for an avatar badge. */
export function initials(email: string): string {
  return email.slice(0, 2).toUpperCase();
}

/** Monday-start ISO date key for the week containing `d`. */
function weekKey(d: Date): string {
  const date = new Date(d);
  const day = (date.getDay() + 6) % 7; // 0 = Monday
  date.setDate(date.getDate() - day);
  return date.toISOString().slice(0, 10);
}

/**
 * Real "consistent planning" streak: consecutive weeks (Monday–Sunday) with
 * at least one logged shift, counting back from the most recent week that
 * has one. Derived entirely from existing shift dates — no backend change,
 * no fabricated number.
 */
export function computeWeekStreak(shiftDates: string[]): number {
  const weeks = new Set(
    shiftDates
      .map((iso) => {
        const d = new Date(iso);
        return Number.isNaN(d.getTime()) ? null : weekKey(d);
      })
      .filter((k): k is string => k !== null)
  );
  if (weeks.size === 0) return 0;

  const sorted = [...weeks].sort().reverse(); // most recent week first
  let streak = 1;
  const cursor = new Date(sorted[0]);
  for (let i = 1; i < sorted.length; i++) {
    cursor.setDate(cursor.getDate() - 7);
    if (sorted[i] === weekKey(cursor)) {
      streak += 1;
    } else {
      break;
    }
  }
  return streak;
}
