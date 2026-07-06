"use client";

import { useEffect, useState } from "react";
import { LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { cn, initials } from "@/lib/utils";

/**
 * Document 05 §Header: orientation without distraction. Logo left, nothing
 * center, profile right. Transparent until the page scrolls, then becomes
 * solid. Height 80px desktop / 64px mobile.
 *
 * Search and Notifications are in the Doc 05/12 spec but are deferred —
 * there's no global search index or notification feed wired up yet, and
 * shipping inert icon buttons for them would fail the "never ship
 * half-finished" rule (Document 09). They'll land once those systems exist.
 */
export function Header() {
  const { user, logout } = useAuth();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        "sticky top-0 z-30 flex h-16 items-center justify-between px-5 transition-colors duration-200 md:h-20 md:px-8",
        scrolled ? "border-b border-border bg-surface/95 backdrop-blur" : "border-b border-transparent bg-transparent"
      )}
    >
      <p className="font-serif text-lg font-medium text-text md:hidden">ShiftIQ</p>
      <div className="hidden md:block" aria-hidden="true" />

      <div className="flex items-center gap-3">
        <span className="hidden max-w-[14rem] truncate text-caption text-muted sm:inline">{user?.email}</span>
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent-light text-xs font-semibold text-accent-dark">
          {user ? initials(user.email) : "?"}
        </span>
        <button
          onClick={logout}
          aria-label="Log out"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-muted transition-colors duration-200 hover:bg-surface-hover hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 md:hidden"
        >
          <LogOut size={18} aria-hidden="true" />
        </button>
      </div>
    </header>
  );
}
