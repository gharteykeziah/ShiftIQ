interface TimelineEvent {
  time: string;
  title: string;
  duration: string;
}

interface TimelineProps {
  events: TimelineEvent[];
  emptyMessage: string;
}

/**
 * Document 02/05/12 §Timeline: vertical, Apple Calendar inspired, never a
 * table. Helps users understand time, not finances.
 */
export function Timeline({ events, emptyMessage }: TimelineProps) {
  if (events.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface p-8">
        <p className="text-sm font-medium text-muted">Today&apos;s timeline</p>
        <p className="mt-3 text-sm text-text">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-8">
      <p className="mb-6 text-sm font-medium text-muted">Today&apos;s timeline</p>
      <ol className="space-y-8">
        {events.map((event, i) => (
          <li key={`${event.time}-${event.title}`} className="animate-fade-up flex gap-4" style={{ animationDelay: `${i * 40}ms` }}>
            <span className="w-16 shrink-0 text-sm font-medium text-muted">{event.time}</span>
            <div className="min-w-0 flex-1 border-l border-border pl-4">
              <p className="text-sm font-medium text-text">{event.title}</p>
              <p className="text-caption text-muted">{event.duration}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
