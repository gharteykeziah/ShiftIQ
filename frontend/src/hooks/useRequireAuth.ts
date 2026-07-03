"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

/**
 * Guard for any page that requires a logged-in user. Redirects to /login
 * once we know for sure there's no valid session (isLoading is false and
 * user is still null) — not before, so a page refresh doesn't flash a
 * redirect while the token is still being verified.
 *
 * Usage in a page component:
 *   const { user, isLoading } = useRequireAuth();
 *   if (isLoading || !user) return <PageSkeleton />;
 */
export function useRequireAuth() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login");
    }
  }, [isLoading, user, router]);

  return { user, isLoading };
}
