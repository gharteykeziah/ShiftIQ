interface JourneyStep {
  label: string;
  amount: string;
  note: string;
}

/**
 * Document 02/05/06/12 §Money Story / Money Journey: replaces charts
 * entirely. Tells where money goes as a simple downward story instead of a
 * pie chart or dashboard of stats.
 */
export function MoneyJourney({ steps }: { steps: JourneyStep[] }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-8 md:p-10">
      <p className="mb-6 text-sm font-medium text-muted">Money this week</p>
      <ol className="space-y-0">
        {steps.map((step, i) => (
          <li key={step.label}>
            <div className="flex items-baseline justify-between gap-4 py-4">
              <div>
                <p className="text-sm font-medium text-text">{step.label}</p>
                <p className="mt-0.5 text-caption text-muted">{step.note}</p>
              </div>
              <p className="shrink-0 font-serif text-card-heading font-medium text-text">{step.amount}</p>
            </div>
            {i < steps.length - 1 && <div className="h-px bg-border" />}
          </li>
        ))}
      </ol>
    </div>
  );
}
