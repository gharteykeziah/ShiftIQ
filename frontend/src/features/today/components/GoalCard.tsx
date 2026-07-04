import { Progress } from "@/components/ui/Progress";

interface GoalCardProps {
  name: string;
  current: string;
  target: string;
  percent: number;
  recommendation: string;
}

/** Document 02/12 §Goal Card: one goal, progress, and a recommendation. Never a pie chart. */
export function GoalCard({ name, current, target, percent, recommendation }: GoalCardProps) {
  return (
    <div className="hover-lift rounded-lg border border-border bg-surface p-8">
      <p className="text-sm font-medium text-muted">{name}</p>
      <p className="mt-2 font-serif text-[28px] font-medium leading-tight text-text">
        {current} <span className="text-body text-muted">/ {target}</span>
      </p>
      <div className="mt-4">
        <Progress value={percent} />
        <p className="mt-1.5 text-caption text-muted">{Math.round(percent)}% complete</p>
      </div>
      <p className="mt-4 text-sm text-text">{recommendation}</p>
    </div>
  );
}
