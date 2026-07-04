import type { LucideIcon } from "lucide-react";
import { LayoutDashboard, Briefcase, CalendarClock, Receipt, TrendingUp, Target } from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

/** Shared by Sidebar (desktop) and BottomNav (mobile) so both stay in sync. */
export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Today", icon: LayoutDashboard },
  { href: "/jobs", label: "Jobs", icon: Briefcase },
  { href: "/shifts", label: "Shifts", icon: CalendarClock },
  { href: "/expenses", label: "Expenses", icon: Receipt },
  { href: "/simulation", label: "Future Check", icon: TrendingUp },
  { href: "/goals", label: "Goals", icon: Target },
];
