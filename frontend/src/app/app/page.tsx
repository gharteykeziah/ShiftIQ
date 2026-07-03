"use client";

import { useRequireAuth } from "@/hooks/useRequireAuth";
import { useAuth } from "@/context/AuthContext";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";

// Temporary landing page for a logged-in user. Days 7-8 replace this with
// the real responsive app shell (sidebar/bottom nav + the six real pages).
// This exists only to prove the auth flow works end to end.
export default function AppHome() {
  const { user, isLoading } = useRequireAuth();
  const { logout } = useAuth();

  if (isLoading || !user) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-bg px-6">
        <div className="w-full max-w-sm space-y-3">
          <Skeleton className="h-6 w-2/3" />
          <Skeleton className="h-24 w-full" />
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-6">
      <Card className="w-full max-w-sm text-center">
        <CardHeader>
          <CardTitle>You&apos;re signed in</CardTitle>
          <CardDescription>{user.email}</CardDescription>
        </CardHeader>
        <p className="mb-6 text-sm text-muted">
          The real dashboard, jobs, shifts, expenses, simulation, and goals pages land in the days
          ahead. This placeholder just confirms the auth flow works end to end.
        </p>
        <Button variant="outline" className="w-full" onClick={logout}>
          Log out
        </Button>
      </Card>
    </main>
  );
}
