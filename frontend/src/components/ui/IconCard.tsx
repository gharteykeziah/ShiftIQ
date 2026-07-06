"use client";

import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface IconCardProps {
  icon: LucideIcon;
  label: string;
  selected?: boolean;
  onClick?: () => void;
  className?: string;
}

/**
 * Icon + label choice card, in the Truebill "choose your top goals" pattern.
 * Used for the Goals page (Weeks to Goal / Goal Progress / Emergency Fund)
 * instead of the tkinter tab bar.
 */
export function IconCard({ icon: Icon, label, selected, onClick, className }: IconCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={cn(
        "flex flex-col items-start gap-3 rounded-2xl p-4 text-left transition-colors duration-150",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:ring-offset-2",
        selected ? "bg-text text-white" : "bg-surface text-text hover:bg-surface-hover",
        className
      )}
    >
      <span
        className={cn(
          "flex h-9 w-9 items-center justify-center rounded-xl",
          selected ? "bg-white/15" : "bg-accent-light"
        )}
      >
        <Icon className={cn("h-5 w-5", selected ? "text-white" : "text-accent")} aria-hidden="true" />
      </span>
      <span className="text-sm font-semibold">{label}</span>
    </button>
  );
}
