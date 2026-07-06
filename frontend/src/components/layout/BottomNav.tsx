"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { MoreHorizontal, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";
import { NAV_ITEMS } from "./nav-items";
import { Drawer } from "@/components/ui/Drawer";

// Document 07 §Mobile Navigation: exactly five tabs, everything else
// behind "More". The four most-used destinations stay direct; Jobs and
// Future Check move into the overflow drawer.
const PRIMARY_HREFS = ["/dashboard", "/shifts", "/goals", "/expenses"];

/** Mobile navigation — fixed to the bottom of the viewport, hidden at/above the md breakpoint. */
export function BottomNav() {
  const pathname = usePathname();
  const { logout } = useAuth();
  const [moreOpen, setMoreOpen] = useState(false);

  const primary = NAV_ITEMS.filter((item) => PRIMARY_HREFS.includes(item.href));
  const overflow = NAV_ITEMS.filter((item) => !PRIMARY_HREFS.includes(item.href));

  return (
    <>
      <nav
        className="fixed inset-x-0 bottom-0 z-40 flex border-t border-border bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
        aria-label="Primary"
      >
        {primary.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex min-h-[44px] flex-1 flex-col items-center gap-1 py-2.5 text-[11px] font-medium transition-colors duration-200",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:ring-inset",
                active ? "text-accent" : "text-muted"
              )}
            >
              <Icon size={20} strokeWidth={2} aria-hidden="true" />
              {label}
            </Link>
          );
        })}
        <button
          onClick={() => setMoreOpen(true)}
          className="flex min-h-[44px] flex-1 flex-col items-center gap-1 py-2.5 text-[11px] font-medium text-muted transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:ring-inset"
          aria-haspopup="dialog"
        >
          <MoreHorizontal size={20} strokeWidth={2} aria-hidden="true" />
          More
        </button>
      </nav>

      <Drawer open={moreOpen} onClose={() => setMoreOpen(false)} title="More">
        <div className="space-y-1">
          {overflow.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              onClick={() => setMoreOpen(false)}
              className="flex min-h-[44px] items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium text-text hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
            >
              <Icon size={20} strokeWidth={2} aria-hidden="true" />
              {label}
            </Link>
          ))}
          <button
            onClick={() => {
              setMoreOpen(false);
              logout();
            }}
            className="flex min-h-[44px] w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm font-medium text-muted hover:bg-surface-hover hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
          >
            <LogOut size={20} strokeWidth={2} aria-hidden="true" />
            Log out
          </button>
        </div>
      </Drawer>
    </>
  );
}
