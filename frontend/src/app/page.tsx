"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

// Now that /dashboard exists (Days 7-8), root routing is auth-aware:
// logged-in users skip onboarding, logged-out visitors see it.
// /components-preview is still reachable directly by URL.
export default function Home() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    router.replace(user ? "/dashboard" : "/onboarding");
  }, [isLoading, user, router]);

  return null;
}
