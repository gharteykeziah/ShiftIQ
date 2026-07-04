import type { ShiftOut } from "@/lib/types";

export type TimeOfDay = "morning" | "afternoon" | "evening";

export function timeOfDay(hour = new Date().getHours()): TimeOfDay {
  if (hour < 12) return "morning";
  if (hour < 18) return "afternoon";
  return "evening";
}

export function greetingWord(hour = new Date().getHours()): TimeOfDay {
  return timeOfDay(hour);
}

export function formatTime12h(time: string): string {
  const [hStr, mStr] = time.split(":");
  const h = Number(hStr);
  const m = Number(mStr);
  const ampm = h < 12 ? "AM" : "PM";
  const h12 = h % 12 || 12;
  return `${h12}:${String(m).padStart(2, "0")} ${ampm}`;
}

function toMinutes(time: string): number {
  const [h, m] = time.split(":").map(Number);
  return h * 60 + m;
}

/**
 * Document 05 revision: "Your first shift starts in 2 hours" / "You're free
 * until 3 PM" — a live, glanceable line computed from the user's actual
 * shifts for today, not a fabricated string. Returns undefined when there's
 * nothing meaningful to say (no shifts today), so the Hero simply omits it.
 */
export function computeContextLine(todayShifts: ShiftOut[], now = new Date()): string | undefined {
  if (todayShifts.length === 0) return undefined;

  const nowMinutes = now.getHours() * 60 + now.getMinutes();
  const sorted = [...todayShifts].sort((a, b) => toMinutes(a.start_time) - toMinutes(b.start_time));

  const current = sorted.find((s) => toMinutes(s.start_time) <= nowMinutes && nowMinutes < toMinutes(s.end_time));
  if (current) {
    return `You're clocked in at ${current.title} until ${formatTime12h(current.end_time)}.`;
  }

  const next = sorted.find((s) => toMinutes(s.start_time) > nowMinutes);
  if (next) {
    const diff = toMinutes(next.start_time) - nowMinutes;
    const hours = Math.floor(diff / 60);
    const minutes = diff % 60;
    const timeLabel = hours > 0 ? `${hours}h${minutes > 0 ? ` ${minutes}m` : ""}` : `${minutes} minutes`;
    return `Your shift at ${next.title} starts in ${timeLabel}.`;
  }

  return "You're free for the rest of today.";
}

export function displayName(email: string): string {
  const local = email.split("@")[0].split(/[._-]/)[0];
  return local.charAt(0).toUpperCase() + local.slice(1);
}

export function money(n: number): string {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function moneyRounded(n: number): string {
  return `$${Math.round(n).toLocaleString()}`;
}

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function formatDateLabel(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function mondayOf(d: Date): Date {
  const date = new Date(d);
  const day = (date.getDay() + 6) % 7; // 0 = Monday
  date.setHours(0, 0, 0, 0);
  date.setDate(date.getDate() - day);
  return date;
}

/** True when `iso` falls in the same Monday–Sunday week as `reference`. */
export function isSameWeek(iso: string, reference = new Date()): boolean {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return false;
  return mondayOf(d).getTime() === mondayOf(reference).getTime();
}
