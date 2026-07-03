"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "./nav-items";

/** Mobile navigation — fixed to the bottom of the viewport, hidden at/above the md breakpoint. */
export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 flex border-t border-border/60 bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
      aria-label="Primary"
    >
      {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex flex-1 flex-col items-center gap-1 py-2.5 text-[11px] font-medium transition-colors duration-150",
              active ? "text-accent" : "text-muted"
            )}
          >
            <Icon className="h-5 w-5" aria-hidden="true" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
