"use client";

import { useState } from "react";
import { ChevronRight } from "lucide-react";

const QUOTES = [
  "Discipline today, freedom tomorrow.",
  "Small, consistent moves beat big, occasional ones.",
  "Every shift you plan is a decision you don't have to make in a panic later.",
  "Progress you can see is progress you'll keep making.",
];

export function QuoteBanner({ className }: { className?: string }) {
  const [i, setI] = useState(0);

  return (
    <div className={`bento-card quote-card wide flex items-center justify-between ${className ?? ""}`}>
      <h2 className="m-0">&ldquo;{QUOTES[i]}&rdquo;</h2>
      <button
        type="button"
        onClick={() => setI((v) => (v + 1) % QUOTES.length)}
        aria-label="Next quote"
        className="ml-4 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--amber)] text-[var(--primary)] transition-transform duration-150 hover:scale-105"
      >
        <ChevronRight className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}
