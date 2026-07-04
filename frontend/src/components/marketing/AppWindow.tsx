import { ReactNode } from "react";

/**
 * Window-chrome frame for marketing previews of the real product — an
 * honest stand-in for lifestyle photography (Document 01 allows photography
 * on the marketing site, but we don't have any; showing the actual product
 * is more honest than stock photos of strangers).
 */
export function AppWindow({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`overflow-hidden rounded-lg border border-border bg-surface shadow-3 ${className}`}>
      <div className="flex items-center gap-1.5 border-b border-border bg-bg px-4 py-3">
        <span className="h-2.5 w-2.5 rounded-full bg-danger/60" />
        <span className="h-2.5 w-2.5 rounded-full bg-warning/60" />
        <span className="h-2.5 w-2.5 rounded-full bg-success/60" />
      </div>
      <div className="p-6">{children}</div>
    </div>
  );
}
