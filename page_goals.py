"""page_goals.py — Goals page (weeks to goal, progress bar, emergency fund)."""
import tkinter as tk

import theme
from theme import F_BODY, F_SMALL, F_H2
from widgets import (ScrollFrame, TabBar, page_title, card, kv_row,
                     labeled_entry, action_btn, status_lbl)


class GoalsPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self._app = app

        header = tk.Frame(self, bg=theme.BG, padx=36, pady=16)
        header.pack(fill="x")
        page_title(header, "Goals", "Track progress toward a savings goal.")

        tb = TabBar(self, [
            ("weeks",     "Weeks to Goal"),
            ("progress",  "Goal Progress"),
            ("emergency", "Emergency Fund"),
        ])
        tb.pack(fill="x", padx=36)
        self._body = tk.Frame(self, bg=theme.BG)
        self._body.pack(fill="both", expand=True)
        tb.bind_select(self._render)
        tb.activate("weeks")

    def _render(self, key):
        for w in self._body.winfo_children():
            w.destroy()
        {"weeks":     self._weeks_to_goal,
         "progress":  self._goal_progress,
         "emergency": self._emergency_fund}[key]()

    # ── Weeks to Goal ─────────────────────────────────────────────────────
    def _weeks_to_goal(self):
        state = self._app.state
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        tk.Label(inner, text="Weeks to Goal", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 8))
        tk.Label(inner,
                 text="Enter a savings target. We will tell you how many weeks it will take "
                      "to reach it at your current net weekly flow.",
                 font=F_SMALL, fg=theme.MUTED, bg=theme.BG,
                 wraplength=600, justify="left").pack(anchor="w", pady=(0, 10))

        goal_e = labeled_entry(inner, "Savings Goal ($)", width=16)
        result = tk.Frame(inner, bg=theme.BG)
        result.pack(anchor="w")

        def calculate():
            for w in result.winfo_children():
                w.destroy()
            try:
                goal = _pf(goal_e, "Goal")
                if goal <= 0:
                    raise ValueError("Goal must be greater than zero.")
                weeks = state.weeks_to_goal(goal)
                if weeks is None:
                    tk.Label(result,
                             text="Your current net weekly flow is zero or negative. "
                                  "This goal cannot be reached without more income or fewer expenses.",
                             font=F_BODY, fg=theme.DANGER, bg=theme.BG,
                             wraplength=600, justify="left").pack(anchor="w", pady=8)
                else:
                    c = card(result, pady=8)
                    kv_row(c, "Goal",            f"${goal:,.2f}")
                    kv_row(c, "Net weekly flow", f"${state.net_weekly_flow():+,.2f}")
                    kv_row(c, "Weeks to goal",   str(weeks), theme.ACCENT)
                    kv_row(c, "That is roughly", f"{weeks/4.33:.1f} months", theme.ACCENT)
            except ValueError as e:
                status_lbl(result, str(e), False)

        action_btn(inner, "Calculate", calculate)

    # ── Goal Progress ─────────────────────────────────────────────────────
    def _goal_progress(self):
        state = self._app.state
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        tk.Label(inner, text="Goal Progress", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 8))
        tk.Label(inner,
                 text="Enter a savings goal and see what percentage you have already saved.",
                 font=F_SMALL, fg=theme.MUTED, bg=theme.BG,
                 wraplength=600, justify="left").pack(anchor="w", pady=(0, 10))

        goal_e = labeled_entry(inner, "Savings Goal ($)", width=16)
        result = tk.Frame(inner, bg=theme.BG)
        result.pack(fill="x")

        def show():
            for w in result.winfo_children():
                w.destroy()
            try:
                goal  = _pf(goal_e, "Goal")
                if goal <= 0:
                    raise ValueError("Goal must be greater than zero.")
                pct   = min(state.goal_progress(goal), 100)
                color = theme.ACCENT if pct >= 50 else ("#e67e22" if pct >= 20 else theme.DANGER)

                c = card(result, pady=8)
                kv_row(c, "Goal",            f"${goal:,.2f}")
                kv_row(c, "Current balance", f"${state.current_balance():,.2f}")
                kv_row(c, "Progress",        f"{pct:.1f}%", color)

                # Progress bar
                bar_frame = tk.Frame(result, bg=theme.BG)
                bar_frame.pack(fill="x", pady=(10, 0))
                tk.Label(bar_frame, text=f"{pct:.0f}% Complete",
                         font=("Inter", 10, "bold"), fg=color, bg=theme.BG).pack(anchor="w")
                bar_bg = tk.Frame(bar_frame, bg=theme.BORDER, height=22)
                bar_bg.pack(fill="x")
                bar_bg.update_idletasks()
                W = bar_bg.winfo_width() or 600
                fill_w  = max(4, int(W * (pct / 100)))
                bar_fill = tk.Frame(bar_bg, bg=color, height=22, width=fill_w)
                bar_fill.place(x=0, y=0)
                tk.Label(bar_bg, text=f"${state.current_balance():,.2f}",
                         font=("Inter", 9, "bold"), fg="white", bg=color
                         ).place(x=max(4, fill_w - 4), y=3, anchor="ne")
            except ValueError as e:
                status_lbl(result, str(e), False)

        action_btn(inner, "Show Progress", show)

    # ── Emergency Fund ────────────────────────────────────────────────────
    def _emergency_fund(self):
        state = self._app.state
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        tk.Label(inner, text="Emergency Fund Calculator", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 8))
        tk.Label(inner,
                 text="An emergency fund covers 3–6 months of expenses so that a job loss, "
                      "medical bill, or car repair does not send you into debt. "
                      "This tool shows your targets and how long it will take to reach them.",
                 font=F_SMALL, fg=theme.MUTED, bg=theme.BG,
                 wraplength=640, justify="left").pack(anchor="w", pady=(0, 14))

        monthly_expenses = state.total_expense_per_week() * (52 / 12)
        target_3x = monthly_expenses * 3
        target_6x = monthly_expenses * 6
        balance   = state.current_balance()
        flow      = state.net_weekly_flow()

        def weeks_label(needed):
            shortfall = needed - balance
            if shortfall <= 0:
                return "Already funded ✓", theme.ACCENT
            if flow <= 0:
                return "Not reachable at current flow", theme.DANGER
            wks = shortfall / flow
            return f"{wks:.0f} weeks  ({wks / 4.33:.1f} months)", theme.TEXT

        c = card(inner, pady=10)
        tk.Label(c, text="Based on your current expenses",
                 font=F_SMALL, fg=theme.MUTED, bg=theme.BG).pack(anchor="w", pady=(0, 6))

        kv_row(c, "Monthly expenses", f"${monthly_expenses:,.2f}")
        kv_row(c, "Current balance",  f"${balance:,.2f}")
        kv_row(c, "Net weekly flow",  f"${flow:+,.2f}")

        tk.Frame(c, bg=theme.BORDER, height=1).pack(fill="x", pady=8)

        lbl_3x, col_3x = weeks_label(target_3x)
        lbl_6x, col_6x = weeks_label(target_6x)

        kv_row(c, "3-month target  ($)",  f"${target_3x:,.2f}", theme.ACCENT)
        kv_row(c, "Time to reach 3×",     lbl_3x, col_3x)
        tk.Frame(c, bg=theme.BORDER, height=1).pack(fill="x", pady=6)
        kv_row(c, "6-month target  ($)",  f"${target_6x:,.2f}", theme.ACCENT)
        kv_row(c, "Time to reach 6×",     lbl_6x, col_6x)

        tk.Frame(c, bg=theme.BORDER, height=1).pack(fill="x", pady=8)

        if balance >= target_6x:
            tip       = "You already have a fully-funded 6-month emergency fund. Great work."
            tip_color = theme.ACCENT
        elif balance >= target_3x:
            tip       = ("You have a 3-month emergency fund, which is the minimum recommended. "
                         "Consider saving up to the 6-month target for more security.")
            tip_color = "#e67e22"
        else:
            tip       = ("Focus on the 3-month target first. Once reached, "
                         "keep contributing until you hit 6 months.")
            tip_color = theme.DANGER
        tk.Label(c, text=f"*  {tip}", font=F_SMALL, fg=tip_color, bg=theme.BG,
                 wraplength=620, justify="left").pack(anchor="w", pady=(0, 4))


# ── Private helpers ───────────────────────────────────────────────────────────
def _pf(entry, name) -> float:
    raw = entry.get().strip()
    if not raw:
        raise ValueError(f"{name} cannot be empty.")
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{name}: please enter a valid number (e.g. 12.50).")
