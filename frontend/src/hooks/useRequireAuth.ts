"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

/**
 * Guard for any page that requires a logged-in user. Redirects to /login
 * once we know for sure there's no valid session (isLoading is false, user
 * is still null, AND there's no pending token that just failed to verify
 * for a transient reason like the backend waking up) — not before, so a
 * page refresh doesn't flash a redirect while the token is still being
 * verified, and a temporary server hiccup doesn't sign the user out.
 *
 * Usage in a page component:
 *   const { user, isLoading, authCheckError, retryAuthCheck } = useRequireAuth();
 *   if (isLoading) return <PageSkeleton />;
 *   if (authCheckError) return <RetryCard onRetry={retryAuthCheck} />;
 *   if (!user) return null; // redirecting
 */
export function useRequireAuth() {
  const { user, isLoading, authCheckError, retryAuthCheck } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user && !authCheckError) {
      router.replace("/login");
    }
  }, [isLoading, user, authCheckError, router]);

  return { user, isLoading, authCheckError, retryAuthCheck };
}
