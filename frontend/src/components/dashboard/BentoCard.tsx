import { HTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

/**
 * Base tile for the dashboard bento grid. Specific cards (HeroDecisionCard,
 * SafeSpendCard, etc.) compose this and override background/padding via
 * className — kept unopinionated about color so light/dark/cream variants
 * all share the same shape, radius, and hover behavior.
 */
export const BentoCard = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, children, ...props }, ref) => (
    <div ref={ref} className={cn("bento-card", className)} {...props}>
      {children}
    </div>
  )
);
BentoCard.displayName = "BentoCard";

// Default tint is green; pass "purple" or "amber" via className to match
// the new design system's per-card icon colors (see shiftiq-redesign.css).
export function IconBadge({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return <span className={cn("card-icon", !/\b(purple|amber|green)\b/.test(className ?? "") && "green", className)}>{children}</span>;
}
