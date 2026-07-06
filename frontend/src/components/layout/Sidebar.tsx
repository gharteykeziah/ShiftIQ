"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut } from "lucide-react";
import { cn, computeWeekStreak, initials } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { NAV_ITEMS } from "./nav-items";

/**
 * Desktop navigation — Document 04 §Sidebar Structure: Logo → Primary Nav →
 * Divider → Spacer → Profile. Width 272px, never collapses. Hidden below
 * the md breakpoint, where BottomNav takes over (Document 07).
 */
export function Sidebar() {
  const pathname = usePathname();
  const { user, token, logout } = useAuth();

  // Real streak — consecutive weeks with at least one logged shift, computed
  // from actual shift dates (see computeWeekStreak). Not a fabricated number.
  const [weekStreak, setWeekStreak] = useState<number | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    api.shifts
      .list(token)
      .then((shifts) => {
        if (cancelled) return;
        setWeekStreak(computeWeekStreak(shifts.map((s) => s.shift_date)));
      })
      .catch(() => {
        // Non-fatal — the streak callout just won't render without this.
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  // `fixed` (not `sticky`) so the sidebar is always pinned to the actual
  // browser viewport — full height, top to bottom — no matter how long the
  // page content is, and regardless of how a screenshot tool renders the
  // page (sticky elements can look "cut off" partway down in full-page
  // capture tools since they only reserve one viewport's worth of height).
  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden h-screen w-[272px] flex-col justify-between border-r border-border bg-surface px-5 py-8 md:flex">
      <div>
        <div className="mb-10 px-2">
          <p className="font-serif text-2xl font-medium text-text">ShiftIQ</p>
          <p className="mt-1 text-caption text-muted">Your next best move.</p>
        </div>

        <nav className="space-y-1">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors duration-200",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40",
                  active ? "bg-nav-selected text-accent" : "text-muted hover:bg-surface-hover hover:text-text"
                )}
              >
                <Icon size={20} strokeWidth={2} aria-hidden="true" />
                {label}
              </Link>
            );
          })}
        </nav>
      </div>

      <div>
        {weekStreak !== null && weekStreak > 0 && (
          <div className="mb-4 rounded-lg bg-accent-light px-5 py-4">
            <p className="text-caption text-muted">You&apos;re building momentum</p>
            <p className="mt-1 font-serif text-xl font-medium text-text">
              {weekStreak} {weekStreak === 1 ? "week" : "weeks"}
            </p>
            <p className="text-caption text-muted">of consistent planning</p>
          </div>
        )}

        <div className="mb-2 flex items-center gap-2 border-t border-border px-2 pt-4">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent-light text-xs font-semibold text-accent-dark">
            {user ? initials(user.email) : "?"}
          </span>
          <p className="truncate text-caption text-muted">{user?.email}</p>
        </div>
        <button
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium text-muted transition-colors duration-200 hover:bg-surface-hover hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
        >
          <LogOut size={20} strokeWidth={2} aria-hidden="true" />
          Log out
        </button>
      </div>
    </aside>
  );
}
