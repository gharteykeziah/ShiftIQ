"use client";

import { useMemo } from "react";

// Document 03/05 §Motivational Quotes: rotate, never overdo. Rotated weekly
// via a stable index derived from the ISO week number, so it's consistent
// for a given user across a session without needing new backend state.
const QUOTES = [
  "Every shift tells a story. You're writing yours one decision at a time.",
  "Small progress still counts.",
  "One smart decision at a time.",
  "You're building something bigger than this week.",
  "Consistency beats intensity.",
  "Time is your greatest investment.",
];

function weekIndex(): number {
  const now = new Date();
  const firstDay = new Date(now.getFullYear(), 0, 1);
  const week = Math.ceil(((now.getTime() - firstDay.getTime()) / 86400000 + firstDay.getDay() + 1) / 7);
  return week % QUOTES.length;
}

export function MotivationalFooter() {
  const quote = useMemo(() => QUOTES[weekIndex()], []);
  return (
    <div className="py-10 text-center">
      <p className="mx-auto max-w-reading font-serif text-body-lg italic text-muted">{quote}</p>
    </div>
  );
}
