interface MoneyCardProps {
  title: string;
  amount: string;
  description: string;
}

/** Document 02/12 §Money Card: one financial fact, presented as a sentence, never a chart. */
export function MoneyCard({ title, amount, description }: MoneyCardProps) {
  return (
    <div className="hover-lift rounded-lg border border-border bg-surface p-8">
      <p className="text-sm font-medium text-muted">{title}</p>
      <p className="mt-2 font-serif text-[40px] font-medium leading-none text-text">{amount}</p>
      <p className="mt-3 text-sm text-muted">{description}</p>
    </div>
  );
}
