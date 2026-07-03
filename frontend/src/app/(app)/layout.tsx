"use client";

import { ReactNode } from "react";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { Sidebar } from "@/components/layout/Sidebar";
import { BottomNav } from "@/components/layout/BottomNav";
import { Skeleton } from "@/components/ui/Skeleton";

// Shared shell for every real page (Dashboard, Jobs, Shifts, Expenses,
// Simulation, Goals) — auth is checked once here rather than per-page.
// The (app) route group name doesn't appear in the URL, so pages inside
// resolve to clean paths like /dashboard, /jobs, etc.
export default function AppLayout({ children }: { children: ReactNode }) {
  const { user, isLoading } = useRequireAuth();

  if (isLoading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg px-6">
        <div className="w-full max-w-sm space-y-3">
          <Skeleton className="h-6 w-2/3" />
          <Skeleton className="h-24 w-full" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-bg md:flex-row">
      <Sidebar />
      <main className="flex-1 pb-20 md:pb-0">{children}</main>
      <BottomNav />
    </div>
  );
}
