"use client";

import { LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

/** Mobile-only top bar — shows the signed-in email and a logout button.
 * The Sidebar (desktop) already has both; BottomNav (mobile) is nav-icons
 * only, so without this there was no way to see who's logged in or sign
 * out on a phone. Hidden at/above the md breakpoint, where Sidebar takes over. */
export function MobileHeader() {
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between border-b border-border/60 bg-surface px-4 py-3 md:hidden">
      <div className="min-w-0">
        <p className="text-sm font-bold text-accent">ShiftIQ</p>
        <p className="truncate text-xs text-muted">{user?.email}</p>
      </div>
      <button
        onClick={logout}
        aria-label="Log out"
        className="flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium text-muted transition-colors duration-150 hover:bg-surface-hover hover:text-danger"
      >
        <LogOut className="h-4 w-4" aria-hidden="true" />
        Log out
      </button>
    </header>
  );
}
