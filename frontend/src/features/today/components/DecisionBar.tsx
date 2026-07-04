"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface DecisionBarProps {
  recommendation: string;
  outcome?: string;
  impact?: string;
  href: string;
}

/**
 * Document 02/05/12 — ShiftIQ's signature component. Always communicates
 * the Next Best Move. Sticky once the Hero scrolls out of view (Document 05
 * §Scroll Behavior); on mobile it's pinned directly below the header at all
 * times (Document 07), so it never depends on scroll position there.
 */
export function DecisionBar({ recommendation, outcome, impact, href }: DecisionBarProps) {
  const [stuck, setStuck] = useState(false);

  useEffect(() => {
    const onScroll = () => setStuck(window.scrollY > 260);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div
      className={cn(
        "sticky top-16 z-20 flex min-h-[72px] flex-wrap items-center gap-x-4 gap-y-2 rounded-md border border-border bg-surface px-5 py-3 transition-shadow duration-200 md:top-20",
        stuck && "shadow-2"
      )}
    >
      <span className="text-metadata font-semibold uppercase tracking-wide text-accent">Next best move</span>
      <p className="flex-1 text-sm font-medium text-text sm:text-body-lg">
        {recommendation}
        {outcome && <span className="ml-2 font-semibold text-accent-dark">{outcome}</span>}
      </p>
      {impact && <p className="hidden text-sm text-muted lg:block">{impact}</p>}
      <Link
        href={href}
        className="ml-auto flex items-center gap-1 text-sm font-medium text-accent transition-colors duration-200 hover:text-accent-dark"
      >
        View <ArrowRight size={16} aria-hidden="true" />
      </Link>
    </div>
  );
}
