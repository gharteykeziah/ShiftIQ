"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";
import { NAV_ITEMS } from "./nav-items";

/** Desktop navigation — hidden below the md breakpoint, where BottomNav takes over. */
export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-border/60 bg-surface px-4 py-6 md:flex">
      <div className="mb-8 px-2 text-xl font-bold text-accent">ShiftIQ</div>

      <nav className="flex-1 space-y-1">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-medium transition-colors duration-150",
                active ? "bg-nav-selected text-accent" : "text-muted hover:bg-surface-hover hover:text-text"
              )}
            >
              <Icon className="h-5 w-5" aria-hidden="true" />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-6 border-t border-border/60 pt-4">
        <p className="truncate px-2 text-xs text-muted">{user?.email}</p>
        <button
          onClick={logout}
          className="mt-2 flex w-full items-center gap-2 rounded-2xl px-3 py-2.5 text-sm font-medium text-muted transition-colors duration-150 hover:bg-surface-hover hover:text-danger"
        >
          <LogOut className="h-4 w-4" aria-hidden="true" />
          Log out
        </button>
      </div>
    </aside>
  );
}
