import { Wallet, ShoppingCart, PiggyBank, ArrowRight, TrendingUp } from "lucide-react";
import { BentoCard, IconBadge } from "./BentoCard";

function money(n: number): string {
  return `$${Math.round(Math.abs(n)).toLocaleString()}`;
}

interface MoneyFlowCardProps {
  earned: number;
  spent: number;
  left: number;
  className?: string;
}

export function MoneyFlowCard({ earned, spent, left, className }: MoneyFlowCardProps) {
  const positive = left >= 0;

  return (
    <BentoCard className={className}>
      <IconBadge className="green">
        <TrendingUp size={20} aria-hidden="true" />
      </IconBadge>
      <p className="card-title">Money flow</p>
      <p className="muted">This week</p>

      <div className="money-flow">
        <div className="flow-node earned">
          <Wallet size={22} aria-hidden="true" />
          <h3>{money(earned)}</h3>
          <p>Earned</p>
        </div>

        <ArrowRight className="flow-arrow" aria-hidden="true" />

        <div className="flow-node used">
          <ShoppingCart size={22} aria-hidden="true" />
          <h3>{money(spent)}</h3>
          <p>Spent</p>
        </div>

        <ArrowRight className="flow-arrow" aria-hidden="true" />

        <div className="flow-node saved">
          <PiggyBank size={22} aria-hidden="true" />
          <h3>
            {positive ? "" : "-"}
            {money(left)}
          </h3>
          <p>Left</p>
        </div>
      </div>

      <div className="soft-banner">
        {positive
          ? `You're ${money(left)} closer to your next goal. Keep it up 💚`
          : `You spent ${money(Math.abs(left))} more than you earned this week.`}
      </div>
    </BentoCard>
  );
}
