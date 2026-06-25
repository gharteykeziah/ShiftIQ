"""
app.py — App class: owns state/engines (dependency injection), builds the
         window, sidebar, navigation, and dark-mode toggle.
"""
import logging
import os
import tkinter as tk
from tkinter import filedialog

import theme
from theme import apply_theme, F_NAV
import activity_log
import database as db
import pdf_report
from financial_state import FinancialState
from scenario_engine import ScenarioEngine
from insight_engine import InsightEngine
from config import APP_NAME, APP_VERSION
from utils import canon_name
import schedule_service

logger = logging.getLogger(__name__)


def _export_csv(state, insight_engine):
    """Standalone CSV export — used by sidebar button."""
    import csv
    import shift_analytics as sa
    from config import PROJECTION_WEEKS
    path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        initialfile="financial_report.csv",
        title="Save Financial Report",
    )
    if not path:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ShiftIQ — Export"])
        writer.writerow([])
        writer.writerow(["SUMMARY"])
        writer.writerow(["Balance",         f"${state.current_balance():.2f}"])
        writer.writerow(["Weekly Income",   f"${state.total_income_per_week():.2f}"])
        writer.writerow(["Weekly Expenses", f"${state.total_expense_per_week():.2f}"])
        writer.writerow(["Net Weekly Flow", f"${state.net_weekly_flow():.2f}"])
        writer.writerow(["Savings Rate",    f"{state.savings_rate()*100:.1f}%"])
        writer.writerow(["Risk Score",      insight_engine.risk_score(state)])
        writer.writerow(["Health Score",    insight_engine.financial_health_score(state)])
        writer.writerow([])
        writer.writerow(["JOBS / INCOME"])
        writer.writerow(["Name", "Amount", "Frequency", "Weekly Equivalent"])
        for job in state.jobs:
            writer.writerow([job.name, f"${job.amount:.2f}",
                             job.frequency, f"${job.weekly_income():.2f}"])
        writer.writerow([])
        writer.writerow(["EXPENSES"])
        writer.writerow(["Name", "Amount/Week", "Category", "Date"])
        for exp in state.expenses:
            writer.writerow([exp.name, f"${exp.amount:.2f}", exp.category, exp.date])
        writer.writerow([])
        writer.writerow(["PROJECTIONS"])
        writer.writerow(["Weeks", "Projected Balance"])
        for wks in PROJECTION_WEEKS:
            writer.writerow([wks, f"${state.project_balance(wks):.2f}"])

        # ── Schedule Summary ──────────────────────────────────────────────
        all_events = db.get_events()
        summary    = sa.date_range_summary(all_events)
        if summary.total_hours > 0:
            writer.writerow([])
            writer.writerow(["SCHEDULE SUMMARY"])
            writer.writerow(["Date Range",    f"{summary.start}  to  {summary.end}"])
            writer.writerow(["Total Hours",   f"{summary.total_hours:.1f} hrs"])
            writer.writerow(["Work Days",     summary.work_days])
            writer.writerow(["Total Earned",  f"${summary.total_income:.2f}"])
            writer.writerow([])
            writer.writerow(["INCOME BY JOB (from schedule)"])
            writer.writerow(["Job", "Hours", "Avg Rate ($/hr)", "Shifts", "Total Earned"])
            for group in summary.job_groups.values():
                writer.writerow([
                    group.name,
                    f"{group.total_hours:.1f}",
                    f"${group.avg_rate:.2f}",
                    len(group.shifts),
                    f"${group.total_income:.2f}",
                ])
            top_days = sa.top_earning_days(all_events, n=5)
            if top_days:
                writer.writerow([])
                writer.writerow(["TOP EARNING DAYS"])
                writer.writerow(["Date", "Income"])
                for date_str, amt in top_days:
                    writer.writerow([date_str, f"${amt:.2f}"])

    activity_log.log(f"Exported financial report to CSV: {os.path.basename(path)}")
    tk.messagebox.showinfo("Export Complete", f"Report saved to:\n{path}")


class App(tk.Tk):
    # ── Construction ──────────────────────────────────────────────────────
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME}  v{APP_VERSION}")
        self.geometry("1040x700")
        self.configure(bg=theme.BG)
        self.resizable(True, True)

        # Owned state / engines (dependency injection)
        self.state          = FinancialState()
        self.scenario_engine = ScenarioEngine()
        self.insight_engine  = InsightEngine()

        self._nav_items      = {}
        self._nav_containers = {}
        self._current_page   = "home"

        self._build_layout()
        self._build_sidebar()
        self.show_page("home")

        # Sync all Work events → Data jobs after window is ready
        self.after(200, self._sync_schedule_jobs)

        # Global touchpad / mouse-wheel scroll handler.
        # Walks up from the widget under the cursor to find the nearest Canvas
        # and scrolls it.  This works on macOS trackpads where per-widget
        # bindings are unreliable.
        def _global_scroll(event):
            import sys
            widget = event.widget
            while widget:
                if widget.__class__.__name__ == "Canvas":
                    try:
                        if sys.platform == "darwin":
                            widget.yview_scroll(int(-1 * event.delta), "units")
                        else:
                            delta = event.delta // 120 or (1 if event.delta > 0 else -1)
                            widget.yview_scroll(int(-1 * delta), "units")
                    except Exception:
                        pass
                    return
                widget = getattr(widget, "master", None)

        self.bind_all("<MouseWheel>", _global_scroll)

    def _sync_schedule_jobs(self) -> None:
        """
        On startup, sync all scheduled Work events → Data jobs.
        Delegates to schedule_service.sync_schedule_to_jobs() so this
        logic is testable without a Tk window.
        """
        try:
            schedule_service.sync_schedule_to_jobs(self.state)
        except Exception:
            pass

    # ── Layout ────────────────────────────────────────────────────────────
    def _build_layout(self):
        self.sidebar_frame = tk.Frame(self, bg=theme.SIDEBAR, width=220)
        self.sidebar_frame.pack(side="left", fill="y")
        self.sidebar_frame.pack_propagate(False)
        tk.Frame(self, bg=theme.BORDER, width=1).pack(side="left", fill="y")
        self.content_area = tk.Frame(self, bg=theme.BG)
        self.content_area.pack(side="left", fill="both", expand=True)

    # ── Sidebar ───────────────────────────────────────────────────────────
    def _build_sidebar(self):
        # Brand header
        brand = tk.Frame(self.sidebar_frame, bg=theme.ACCENT, pady=22)
        brand.pack(fill="x")
        tk.Label(brand, text="ShiftIQ", font=("Inter", 22, "bold"),
                 fg="white", bg=theme.ACCENT).pack(anchor="w", padx=20)
        tk.Label(brand, text="Schedule-driven financial intelligence",
                 font=("Inter", 9), fg="#b2f0d0", bg=theme.ACCENT).pack(anchor="w", padx=20)

        tk.Frame(self.sidebar_frame, bg=theme.BORDER, height=1).pack(fill="x")
        tk.Frame(self.sidebar_frame, bg=theme.SIDEBAR, height=6).pack(fill="x")

        # Collapsed to 3 items per FRE_MLP_Product_Strategy.md — Dashboard,
        # Analytics, Forecasting, Goals, Data, and Settings all still exist
        # and still work; they're one tap away via "More" instead of
        # competing with Home and Schedule for sidebar space.
        nav = [
            ("home",     "⌂  Home"),
            ("schedule", "◷  Schedule"),
            ("more",     "☰  More"),
        ]
        # Use Labels instead of Buttons — Labels always respect fg/bg on macOS.
        for key, label in nav:
            ctr = tk.Frame(self.sidebar_frame, bg=theme.SIDEBAR, cursor="hand2")
            ctr.pack(fill="x", pady=1)
            ind = tk.Frame(ctr, bg=theme.SIDEBAR, width=4)
            ind.pack(side="left", fill="y")
            lbl = tk.Label(
                ctr, text=f"  {label}",
                font=F_NAV, fg=theme.TEXT, bg=theme.SIDEBAR,
                anchor="w", pady=11,
            )
            lbl.pack(side="left", fill="x", expand=True, padx=(4, 8))

            def _enter(e, b=lbl, c=ctr, i=ind):
                if b.cget("fg") != theme.ACCENT:
                    b.config(bg=theme.NAV_SEL, fg=theme.ACCENT)
                c.config(bg=theme.NAV_SEL)
                i.config(bg=theme.ACCENT)

            def _leave(e, k=key):
                self._restore_nav_item(k)

            def _click(e, k=key):
                self.show_page(k)

            for w in (lbl, ctr, ind):
                w.bind("<Enter>", _enter)
                w.bind("<Leave>", _leave)
                w.bind("<Button-1>", _click)

            self._nav_items[key]      = lbl
            self._nav_containers[key] = (ctr, ind)

        # Bottom action labels
        tk.Frame(self.sidebar_frame, bg=theme.BORDER, height=1).pack(fill="x", side="bottom")
        tk.Frame(self.sidebar_frame, bg=theme.SIDEBAR, height=4).pack(fill="x", side="bottom")

        dark_label = "  ☀  Light Mode" if theme.is_dark() else "  ☾  Dark Mode"
        for txt, fg_col, cmd in [
            (dark_label,        theme.MUTED,  self._toggle_dark_mode),
            ("  Backup DB",     theme.MUTED,  self._backup_db),
            ("  Export PDF",    theme.ACCENT, self._export_pdf),
            ("  Export CSV",    theme.BLUE,
             lambda: _export_csv(self.state, self.insight_engine)),
        ]:
            b = tk.Label(
                self.sidebar_frame, text=txt,
                font=("Inter", 10), fg=fg_col, bg=theme.SIDEBAR,
                anchor="w", pady=9, cursor="hand2",
            )
            b.pack(fill="x", padx=6, side="bottom")
            b.bind("<Enter>", lambda e, w=b: w.config(bg=theme.NAV_SEL))
            b.bind("<Leave>", lambda e, w=b: w.config(bg=theme.SIDEBAR))
            b.bind("<Button-1>", lambda e, c=cmd: c())

    def _restore_nav_item(self, key):
        """Revert hover state for one nav item (used on <Leave>)."""
        if key == self._current_page:
            return   # active page keeps its highlight
        btn        = self._nav_items[key]
        ctr, ind   = self._nav_containers[key]
        btn.config(bg=theme.SIDEBAR, fg=theme.TEXT)
        ctr.config(bg=theme.SIDEBAR)
        ind.config(bg=theme.SIDEBAR)

    # Pages reachable only via "More" — keep its nav item highlighted
    # while any of these are on screen, instead of showing no selection.
    _SECONDARY_PAGES = {
        "dashboard", "data_management", "analytics",
        "forecasting", "goals", "settings",
    }

    def _set_active_nav(self, key):
        if key in self._SECONDARY_PAGES:
            key = "more"
        for k, btn in self._nav_items.items():
            ctr, ind = self._nav_containers[k]
            if k == key:
                btn.config(bg=theme.NAV_SEL, fg=theme.ACCENT,
                           font=("Inter", 11, "bold"))
                ind.config(bg=theme.ACCENT)
                ctr.config(bg=theme.NAV_SEL)
            else:
                btn.config(bg=theme.SIDEBAR, fg=theme.TEXT, font=F_NAV)
                ind.config(bg=theme.SIDEBAR)
                ctr.config(bg=theme.SIDEBAR)

    # ── Navigation ────────────────────────────────────────────────────────
    def show_page(self, key):
        for w in self.content_area.winfo_children():
            w.destroy()
        self._set_active_nav(key)
        self._current_page = key

        # Lazy imports — avoids circular deps at module load
        from page_home       import HomePage
        from page_more       import MorePage
        from page_dashboard import DashboardPage
        from page_schedule  import SchedulePage
        from page_data       import DataManagementPage
        from page_analytics  import AnalyticsPage
        from page_forecast   import ForecastingPage
        from page_goals      import GoalsPage
        from page_settings   import SettingsPage

        # "home" and "schedule" are the primary surfaces; everything below
        # "more" is still fully registered and reachable, just not in the
        # main nav. MorePage links to each of these keys directly.
        pages = {
            "home":            HomePage,
            "more":            MorePage,
            "dashboard":       DashboardPage,
            "schedule":        SchedulePage,
            "data_management": DataManagementPage,
            "analytics":       AnalyticsPage,
            "forecasting":     ForecastingPage,
            "goals":           GoalsPage,
            "settings":        SettingsPage,
        }
        pages[key](self.content_area, self).pack(fill="both", expand=True)

    # ── Theme toggle ──────────────────────────────────────────────────────
    def _toggle_dark_mode(self):
        apply_theme(not theme.is_dark())
        # Update root and all top-level container backgrounds
        self.configure(bg=theme.BG)
        self.sidebar_frame.configure(bg=theme.SIDEBAR)
        self.content_area.configure(bg=theme.BG)
        # Also update the 1px border divider between sidebar and content
        for w in self.winfo_children():
            if isinstance(w, tk.Frame) and w not in (
                self.sidebar_frame, self.content_area
            ):
                w.configure(bg=theme.BORDER)
        # Rebuild sidebar children with new theme colors
        for w in self.sidebar_frame.winfo_children():
            w.destroy()
        self._nav_items      = {}
        self._nav_containers = {}
        self._build_sidebar()
        self._set_active_nav(self._current_page)
        # Rebuild current page
        for w in self.content_area.winfo_children():
            w.destroy()
        self.show_page(self._current_page)

    # ── Sidebar actions ───────────────────────────────────────────────────
    def _export_pdf(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile="financial_report.pdf",
            title="Save PDF Report",
        )
        if not path:
            return
        try:
            pdf_report.generate_pdf_report(self.state, self.insight_engine, path)
            activity_log.log(f"Exported PDF report: {os.path.basename(path)}")
            tk.messagebox.showinfo("Export Complete", f"PDF saved to:\n{path}")
        except Exception as e:
            logger.error("PDF export failed: %s", e, exc_info=True)
            tk.messagebox.showerror("Export Failed", str(e))

    def _backup_db(self):
        try:
            dest = db.backup_database()
            activity_log.log(f"Database backed up to: {os.path.basename(dest)}")
            tk.messagebox.showinfo("Backup Complete", f"Database backed up to:\n{dest}")
        except Exception as e:
            logger.error("Database backup failed: %s", e, exc_info=True)
            tk.messagebox.showerror("Backup Failed", str(e))
