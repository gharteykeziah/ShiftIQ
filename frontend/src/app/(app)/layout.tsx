"use client";

import { ReactNode } from "react";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { Sidebar } from "@/components/layout/Sidebar";
import { BottomNav } from "@/components/layout/BottomNav";
import { MobileHeader } from "@/components/layout/MobileHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";

// Shared shell for every real page (Dashboard, Jobs, Shifts, Expenses,
// Simulation, Goals) — auth is checked once here rather than per-page.
// The (app) route group name doesn't appear in the URL, so pages inside
// resolve to clean paths like /dashboard, /jobs, etc.
export default function AppLayout({ children }: { children: ReactNode }) {
  const { user, isLoading, authCheckError, retryAuthCheck } = useRequireAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg px-6">
        <div className="w-full max-w-sm space-y-3">
          <Skeleton className="h-6 w-2/3" />
          <Skeleton className="h-24 w-full" />
        </div>
      </div>
    );
  }

  if (authCheckError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg px-6">
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>Reconnecting&hellip;</CardTitle>
            <CardDescription>{authCheckError}</CardDescription>
          </CardHeader>
          <Button onClick={retryAuthCheck}>Try again</Button>
        </Card>
      </div>
    );
  }

  if (!user) {
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
    <div className="flex min-h-screen w-full min-w-0 flex-col bg-bg md:flex-row">
      <Sidebar />
      {/* min-w-0 is required here: without it, a horizontally-scrolling child
          further down the tree (e.g. the day-filter chips on Shifts) can
          force this flex item to grow to content width instead of staying
          capped at the viewport, which is what was pushing the whole page
          off-screen to the right on mobile. */}
      <div className="flex min-w-0 flex-1 flex-col">
        <MobileHeader />
        <main className="min-w-0 flex-1 pb-20 md:pb-0">{children}</main>
      </div>
      <BottomNav />
    </div>
  );
}
