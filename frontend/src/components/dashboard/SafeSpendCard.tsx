import { Wallet } from "lucide-react";
import { BentoCard, IconBadge } from "./BentoCard";

function money(n: number): string {
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

interface SafeSpendCardProps {
  amount: number;
  caption: string;
  className?: string;
}

export function SafeSpendCard({ amount, caption, className }: SafeSpendCardProps) {
  return (
    <BentoCard className={className}>
      <IconBadge className="green">
        <Wallet size={20} aria-hidden="true" />
      </IconBadge>
      <p className="card-title">Safe to spend today</p>
      <h2 className="big-money">{money(amount)}</h2>
      <p className="muted">{caption}</p>
    </BentoCard>
  );
}
