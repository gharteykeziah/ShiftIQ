import Link from "next/link";
import { Sparkles, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface HeroDecisionCardProps {
  eyebrow: string;
  headline: React.ReactNode;
  primaryLabel: string;
  primaryHref: string;
  secondaryLabel?: string;
  secondaryHref?: string;
  className?: string;
}

/**
 * The dashboard's lead card — "your next best move." Background is a CSS
 * gradient + soft blurred shapes standing in for a photo/illustration; swap
 * the decorative div below for a real image whenever art is ready without
 * touching layout or copy logic.
 */
export function HeroDecisionCard({
  eyebrow,
  headline,
  primaryLabel,
  primaryHref,
  secondaryLabel,
  secondaryHref,
  className,
}: HeroDecisionCardProps) {
  return (
    <div className={cn("hero-card", className)}>
      <div>
        <p className="eyebrow">
          <Sparkles className="mr-1.5 inline h-3.5 w-3.5" aria-hidden="true" />
          {eyebrow}
        </p>
        <h2>{headline}</h2>

        <div className="hero-actions">
          <Link href={primaryHref} className="primary-btn">
            {primaryLabel}
            <ArrowRight size={18} aria-hidden="true" />
          </Link>
          {secondaryLabel && secondaryHref && (
            <Link href={secondaryHref} className="secondary-btn">
              {secondaryLabel}
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
