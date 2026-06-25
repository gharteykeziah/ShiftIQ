"""
page_home.py — MLP Home page.

Single-screen decision surface, per FRE_MLP_Product_Strategy.md:
  - One headline number (net weekly flow), framed as an outcome
  - One plain-English stability badge instead of a numeric score
  - This week's Work shifts, each tappable to reveal shift_impact()
    inline — no navigation, no extra screen
  - One secondary action: run the existing knapsack optimizer against
    this week's shifts under a user-given hour budget

This file contains ZERO new financial logic. Every number on screen is a
direct call into financial_state.py, insight_engine.py,
schedule_analytics.py, or optimizer.py — all of which existed before this
page and are already covered by test_fre.py.
"""
from __future__ import annotations

import datetime
import tkinter as tk

import theme
from theme import F_BODY, F_SMALL, F_H2
from widgets import ScrollFrame, page_title, card, action_btn, get_float
import database as db
import shift_analytics as sa
from optimizer import optimize_shift_selection, candidates_from_events

_BADGE_COLOR = {
    "Very Stable":  "#1B6B3A",
    "Stable":       "#1B6B3A",
    "Moderate Risk": "#D97706",
    "High Risk":    "#C0392B",
}


def _week_start(today: datetime.date | None = None) -> datetime.date:
    today = today or datetime.date.today()
    return today - datetime.timedelta(days=today.weekday())


class HomePage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self._app = app
        self._hours_entry: tk.Entry | None = None
        self._optimizer_result: tk.Frame | None = None

        sf = ScrollFrame(self)
        sf.pack(fill="both", expand=True)
        self._build(sf.inner)

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self, inner: tk.Frame) -> None:
        inner.configure(padx=36, pady=28)

        state          = self._app.state
        insight_engine = self._app.insight_engine
        net            = state.net_weekly_flow()
        risk           = insight_engine.risk_score(state)
        risk_label     = insight_engine.risk_label(risk)

        page_title(inner, "Home", "What your schedule is worth this week.")

        # ── Headline ─────────────────────────────────────────────────────────
        hero = tk.Frame(inner, bg=theme.ACCENT, pady=22, padx=24)
        hero.pack(fill="x", pady=(0, 16))

        if net >= 0:
            headline = f"You're on track to net ${net:,.2f} this week."
        else:
            headline = f"You're on track to run a ${abs(net):,.2f} deficit this week."

        tk.Label(hero, text=headline, font=("Inter", 19, "bold"), fg="white",
                 bg=theme.ACCENT, wraplength=640, justify="left").pack(anchor="w")

        badge_color = _BADGE_COLOR.get(risk_label, theme.ACCENT)
        badge = tk.Frame(hero, bg=badge_color)
        badge.pack(anchor="w", pady=(10, 0))
        tk.Label(badge, text=f"  {risk_label}  ", font=("Inter", 10, "bold"),
                 fg="white", bg=badge_color).pack(padx=1, pady=3)

        # ── This week's shifts ───────────────────────────────────────────────
        tk.Label(inner, text="This Week's Shifts", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(20, 8))

        week_start = _week_start()
        events = [
            e for e in db.get_events_for_week(week_start)
            if e.category == "Work"
        ]
        events.sort(key=lambda e: (e.shift_date, e.start_time))

        if not events:
            empty = card(inner)
            tk.Label(
                empty,
                text="No Work shifts scheduled this week. Add or import your "
                     "schedule on the Schedule tab to see your week here.",
                font=F_BODY, fg=theme.MUTED, bg=theme.SIDEBAR, wraplength=660,
                justify="left", padx=16, pady=14,
            ).pack(anchor="w")
        else:
            for ev in events:
                self._shift_row(inner, ev, state)

        # ── Optimizer entry point ────────────────────────────────────────────
        tk.Label(inner, text="Plan Your Hours", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(22, 8))

        opt_card = card(inner)
        tk.Label(
            opt_card,
            text="If you could only work a limited number of hours this week, "
                 "which of your scheduled shifts should you keep to earn the most?",
            font=F_BODY, fg=theme.TEXT, bg=theme.SIDEBAR, wraplength=660,
            justify="left", padx=16,
        ).pack(anchor="w", pady=(14, 6))

        row = tk.Frame(opt_card, bg=theme.SIDEBAR, padx=16, pady=8)
        row.pack(anchor="w", fill="x")
        tk.Label(row, text="Hour budget:", font=F_BODY,
                 fg=theme.TEXT, bg=theme.SIDEBAR).pack(side="left")
        self._hours_entry = tk.Entry(
            row, font=F_BODY, width=6, relief="flat",
            highlightbackground=theme.ACCENT, highlightthickness=1,
            bg=theme.BG, fg=theme.TEXT, insertbackground=theme.TEXT,
        )
        self._hours_entry.insert(0, "20")
        self._hours_entry.pack(side="left", padx=8, ipady=4)

        self._optimizer_result = tk.Frame(opt_card, bg=theme.SIDEBAR)
        self._optimizer_result.pack(fill="x", padx=16, pady=(0, 4))

        action_btn(opt_card, "Optimize My Hours",
                   lambda: self._run_optimizer(events))
        tk.Frame(opt_card, bg=theme.SIDEBAR, height=6).pack()

    # ── Tap-a-shift row ──────────────────────────────────────────────────────
    def _shift_row(self, parent: tk.Frame, ev, state) -> None:
        row_card = card(parent, pady=4)

        top = tk.Frame(row_card, bg=theme.SIDEBAR, padx=16, pady=12, cursor="hand2")
        top.pack(fill="x")

        left = tk.Frame(top, bg=theme.SIDEBAR, cursor="hand2")
        left.pack(side="left", fill="x", expand=True)

        title_lbl = tk.Label(left, text=ev.title, font=("Inter", 12, "bold"),
                              fg=theme.TEXT, bg=theme.SIDEBAR, cursor="hand2")
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(left, text=f"{ev.shift_date or ev.day}  •  {ev.display_time()}",
                            font=F_SMALL, fg=theme.MUTED, bg=theme.SIDEBAR, cursor="hand2")
        sub_lbl.pack(anchor="w")

        toggle_lbl = tk.Label(top, text="What if I skip this?  ›",
                               font=("Inter", 10, "bold"), fg=theme.ACCENT,
                               bg=theme.SIDEBAR, cursor="hand2")
        toggle_lbl.pack(side="right")

        detail_holder = tk.Frame(row_card, bg=theme.SIDEBAR)
        detail_holder.pack(fill="x")

        def toggle(_event=None) -> None:
            if detail_holder.winfo_children():
                for w in detail_holder.winfo_children():
                    w.destroy()
                toggle_lbl.config(text="What if I skip this?  ›")
                return

            impact = sa.shift_impact(ev, state)
            toggle_lbl.config(text="Hide  ⌃")

            box = tk.Frame(detail_holder, bg=theme.ACCENT_L, padx=16, pady=12)
            box.pack(fill="x", padx=16, pady=(0, 14))

            sign = "-" if impact.income_lost >= 0 else "+"
            tk.Label(
                box,
                text=f"Skip this shift: {sign}${abs(impact.income_lost):.2f}  "
                     f"({impact.weekly_income_pct_change:+.1f}% this week)",
                font=("Inter", 11, "bold"), fg=theme.TEXT, bg=theme.ACCENT_L,
                wraplength=600, justify="left",
            ).pack(anchor="w")

            tk.Label(
                box, text=impact.recommendation, font=F_SMALL,
                fg=theme.TEXT, bg=theme.ACCENT_L, wraplength=600, justify="left",
            ).pack(anchor="w", pady=(4, 0))

        for widget in (top, left, title_lbl, sub_lbl, toggle_lbl):
            widget.bind("<Button-1>", toggle)

    # ── Optimizer action ─────────────────────────────────────────────────────
    def _run_optimizer(self, events: list) -> None:
        for w in self._optimizer_result.winfo_children():
            w.destroy()

        try:
            max_hours = get_float(self._hours_entry, "Hour budget")
        except ValueError as e:
            tk.Label(self._optimizer_result, text=str(e), font=F_SMALL,
                     fg=theme.DANGER, bg=theme.SIDEBAR).pack(anchor="w", pady=(6, 0))
            return

        candidates = candidates_from_events(events)
        result = optimize_shift_selection(candidates, max_hours=max_hours)

        if not result.selected:
            tk.Label(
                self._optimizer_result,
                text="No combination of this week's shifts fits that many hours.",
                font=F_BODY, fg=theme.MUTED, bg=theme.SIDEBAR,
            ).pack(anchor="w", pady=(6, 0))
            return

        tk.Label(
            self._optimizer_result,
            text=f"Best combination within {max_hours:.0f}h: "
                 f"${result.total_income:.2f} using {result.total_hours:.1f}h "
                 f"({result.hours_unused:.1f}h unused)",
            font=("Inter", 11, "bold"), fg=theme.ACCENT, bg=theme.SIDEBAR,
            wraplength=660, justify="left",
        ).pack(anchor="w", pady=(6, 4))

        for c in result.selected:
            tk.Label(
                self._optimizer_result,
                text=f"  •  {c.job_name} — {c.hours:.1f}h @ "
                     f"${c.hourly_rate:.2f}/hr = ${c.income:.2f}",
                font=F_SMALL, fg=theme.TEXT, bg=theme.SIDEBAR,
            ).pack(anchor="w")
