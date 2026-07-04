"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface ProgressProps {
  /** 0-100 */
  value: number;
  className?: string;
  trackClassName?: string;
}

/**
 * Document 02/12 §Progress: linear only, never a ring or gauge. 8px height,
 * fully rounded, animates from 0 to its value on mount/update rather than
 * snapping — Document 05 §Animations: "Progress — Animate 0 → value."
 */
export function Progress({ value, className, trackClassName }: ProgressProps) {
  const clamped = Math.min(100, Math.max(0, value));
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    const frame = requestAnimationFrame(() => setDisplay(clamped));
    return () => cancelAnimationFrame(frame);
  }, [clamped]);

  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(clamped)}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn("h-2 w-full overflow-hidden rounded-pill bg-border", trackClassName)}
    >
      <div
        className={cn("h-full rounded-pill bg-accent transition-[width] duration-[400ms] ease-out", className)}
        style={{ width: `${display}%` }}
      />
    </div>
  );
}
