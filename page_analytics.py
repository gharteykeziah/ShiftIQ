"""page_analytics.py — Analytics page (savings, health, income, categories, trends)."""
import tkinter as tk

import theme
import database as db
import charts
import shift_analytics as sa
from theme import F_BODY, F_SMALL, F_H2
from widgets import ScrollFrame, TabBar, page_title, card, kv_row


class AnalyticsPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self._app = app

        header = tk.Frame(self, bg=theme.BG, padx=36, pady=16)
        header.pack(fill="x")
        page_title(header, "Analytics", "Understand your savings, health, and spending.")

        tb = TabBar(self, [
            ("savings",    "Savings"),
            ("health",     "Health"),
            ("income",     "Income"),
            ("categories", "Expenses"),
            ("trends",     "Trends"),
        ])
        tb.pack(fill="x", padx=36)
        self._body = tk.Frame(self, bg=theme.BG)
        self._body.pack(fill="both", expand=True)
        tb.bind_select(self._render)
        tb.activate("savings")

    def _render(self, key):
        for w in self._body.winfo_children():
            w.destroy()
        {"savings":    self._savings,
         "health":     self._health,
         "income":     self._income,
         "categories": self._categories,
         "trends":     self._trends}[key]()

    # ── Savings ───────────────────────────────────────────────────────────
    def _savings(self):
        state = self._app.state
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        sr    = state.savings_rate()
        color = theme.ACCENT if sr >= 0.1 else theme.DANGER

        tk.Label(inner, text="Savings Rate", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 12))

        hero = tk.Frame(inner, bg=theme.SIDEBAR,
                        highlightbackground=theme.BORDER, highlightthickness=1,
                        padx=24, pady=20)
        hero.pack(anchor="w")
        tk.Label(hero, text=f"{sr*100:.1f}%", font=("Inter", 36, "bold"),
                 fg=color, bg=theme.SIDEBAR).pack(anchor="w")
        tk.Label(hero, text="of your weekly income is saved",
                 font=F_BODY, fg=theme.MUTED, bg=theme.SIDEBAR).pack(anchor="w", pady=(2, 0))

        c = card(inner, pady=10)
        for key, val in [
            ("Weekly Income",   f"${state.total_income_per_week():,.2f}"),
            ("Weekly Expenses", f"${state.total_expense_per_week():,.2f}"),
            ("Net Weekly Flow", f"${state.net_weekly_flow():+,.2f}"),
        ]:
            kv_row(c, key, val)

        if sr < 0:
            note = "You are spending more than you earn. Try reducing an expense or picking up more hours."
        elif sr < 0.1:
            note = "Your savings rate is low. Aim for at least 10–20% if possible."
        elif sr < 0.2:
            note = "Acceptable savings rate. Pushing toward 20% gives you a stronger safety net."
        else:
            note = "Great savings rate! You are building financial stability."
        tk.Label(inner, text=note, font=F_BODY, fg=theme.MUTED, bg=theme.BG,
                 wraplength=600, justify="left").pack(anchor="w", pady=(12, 0))

    # ── Health ────────────────────────────────────────────────────────────
    def _health(self):
        state          = self._app.state
        insight_engine = self._app.insight_engine
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        health  = insight_engine.financial_health_score(state)
        risk    = insight_engine.risk_score(state)
        h_color = theme.ACCENT if health >= 60 else ("#e67e22" if health >= 40 else theme.DANGER)
        r_color = theme.ACCENT if risk   >= 60 else ("#e67e22" if risk   >= 40 else theme.DANGER)

        tk.Label(inner, text="Financial Health", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 12))

        scores_row = tk.Frame(inner, bg=theme.BG)
        scores_row.pack(anchor="w")
        for label, score, color, lbl_fn in [
            ("Health Score", health, h_color, insight_engine.health_label),
            ("Risk Score",   risk,   r_color, insight_engine.risk_label),
        ]:
            sc = tk.Frame(scores_row, bg=theme.SIDEBAR,
                          highlightbackground=theme.BORDER, highlightthickness=1,
                          padx=22, pady=16)
            sc.pack(side="left", padx=(0, 12))
            tk.Label(sc, text=label,      font=F_SMALL, fg=theme.MUTED, bg=theme.SIDEBAR).pack(anchor="w")
            tk.Label(sc, text=str(score), font=("Inter", 32, "bold"),
                     fg=color, bg=theme.SIDEBAR).pack(anchor="w")
            tk.Label(sc, text=lbl_fn(score), font=F_BODY,
                     fg=color, bg=theme.SIDEBAR).pack(anchor="w")

        # Score Breakdown
        tk.Label(inner, text="Score Breakdown", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(18, 6))
        tk.Label(inner,
                 text="Each factor below contributes to your Health and Risk scores.",
                 font=F_SMALL, fg=theme.MUTED, bg=theme.BG).pack(anchor="w", pady=(0, 8))

        bc       = card(inner, pady=8)
        income   = state.total_income_per_week()
        expenses = state.total_expense_per_week()
        sr_val   = state.savings_rate()
        flow     = state.net_weekly_flow()
        bal      = state.current_balance()

        if   sr_val >= 0.30: hs_band, hs_pts, hs_col = "≥ 30%  (Strong)",    "+90", theme.ACCENT
        elif sr_val >= 0.20: hs_band, hs_pts, hs_col = "≥ 20%  (Good)",      "+75", theme.ACCENT
        elif sr_val >= 0.10: hs_band, hs_pts, hs_col = "≥ 10%  (OK)",        "+60", "#e67e22"
        elif sr_val >= 0:    hs_band, hs_pts, hs_col = "0–10%  (Minimal)",   "+50", "#e67e22"
        else:                hs_band, hs_pts, hs_col = "Negative (Deficit)", "+20", theme.DANGER

        tk.Label(bc, text="Health Score", font=("Inter", 11, "bold"),
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", padx=16, pady=(6, 2))
        kv_row(bc, f"Savings rate  ({sr_val*100:.1f}%)", f"{hs_band}  →  {hs_pts} pts", hs_col)

        tk.Frame(bc, bg=theme.BORDER, height=1).pack(fill="x", pady=6)

        tk.Label(bc, text="Risk Score  (starts at 50)", font=("Inter", 11, "bold"),
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", padx=16, pady=(0, 2))

        risk_factors = []
        if flow < 0:
            risk_factors.append(("Net flow is negative", "−20 pts", theme.DANGER))
        if income > 0 and expenses / income > 0.8:
            ratio = expenses / income * 100
            risk_factors.append((f"Expense ratio {ratio:.0f}%  (> 80%)", "−15 pts", theme.DANGER))
        if sr_val >= 0.20:
            risk_factors.append(("Savings rate ≥ 20%", "+20 pts", theme.ACCENT))
        elif sr_val >= 0.10:
            risk_factors.append(("Savings rate ≥ 10%", "+10 pts", theme.ACCENT))
        elif sr_val < 0:
            risk_factors.append(("Savings rate negative", "−25 pts", theme.DANGER))
        if bal <= 0:
            risk_factors.append(("Balance ≤ 0", "−10 pts", theme.DANGER))

        if risk_factors:
            for label, pts, col in risk_factors:
                kv_row(bc, label, pts, col)
        else:
            kv_row(bc, "No negative factors", "Base 50 pts", theme.ACCENT)

        # All insights
        tk.Label(inner, text="All Insights", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(18, 6))
        insights = insight_engine.generate_insights(state)
        if insights:
            ic = card(inner)
            for i, txt in enumerate(insights, 1):
                row_f = tk.Frame(ic, bg=theme.SIDEBAR)
                row_f.pack(fill="x", padx=16, pady=6)
                tk.Label(row_f, text=str(i), font=("Inter", 10, "bold"),
                         fg=theme.ACCENT, bg=theme.ACCENT_L,
                         width=2, pady=2).pack(side="left", padx=(0, 10))
                tk.Label(row_f, text=txt, font=F_BODY,
                         fg=theme.TEXT, bg=theme.SIDEBAR,
                         wraplength=620, justify="left").pack(side="left")
        else:
            tk.Label(inner, text="Add jobs and expenses to generate insights.",
                     font=F_BODY, fg=theme.MUTED, bg=theme.BG).pack(anchor="w")

    # ── Income ────────────────────────────────────────────────────────────
    def _income(self):
        state  = self._app.state
        sf     = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner  = sf.inner
        inner.configure(padx=36, pady=20)

        tk.Label(inner, text="Income Breakdown", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 4))

        # ── Schedule-based breakdown (rich data) ──────────────────────────
        all_events  = db.get_events()
        job_groups  = sa.income_by_job(all_events)
        total_sched = sum(g.total_income for g in job_groups.values())

        if job_groups:
            tk.Label(inner,
                     text="From scheduled shifts — actual hours and rates from your calendar.",
                     font=F_SMALL, fg=theme.MUTED, bg=theme.BG).pack(anchor="w", pady=(0, 10))

            c = card(inner)
            hdr = tk.Frame(c, bg=theme.ACCENT)
            hdr.pack(fill="x")
            for txt, w in [("Job", 18), ("$/hr", 8), ("Hours", 8),
                           ("Shifts", 8), ("Total Earned", 14)]:
                tk.Label(hdr, text=txt, font=("Inter", 10, "bold"), fg="white",
                         bg=theme.ACCENT, width=w, anchor="w").pack(side="left", padx=8, pady=5)

            for i, (key, group) in enumerate(job_groups.items()):
                bg_row = theme.SIDEBAR if i % 2 == 0 else theme.ACCENT_L
                row    = tk.Frame(c, bg=bg_row,
                                  highlightbackground=theme.BORDER, highlightthickness=1)
                row.pack(fill="x", pady=1)
                pct = (group.total_income / total_sched * 100) if total_sched else 0
                for val, w in [
                    (group.name,                   18),
                    (f"${group.avg_rate:.2f}",      8),
                    (f"{group.total_hours:.1f}h",   8),
                    (str(len(group.shifts)),         8),
                    (f"${group.total_income:,.2f}  ({pct:.0f}%)", 18),
                ]:
                    tk.Label(row, text=val, font=("Inter", 10),
                             fg=theme.TEXT, bg=bg_row,
                             width=w, anchor="w").pack(side="left", padx=8, pady=6)

            total_row = tk.Frame(c, bg=theme.ACCENT)
            total_row.pack(fill="x", pady=(2, 0))
            tk.Label(total_row, text="Total Scheduled Income", font=("Inter", 11, "bold"),
                     fg="white", bg=theme.ACCENT,
                     width=18, anchor="w").pack(side="left", padx=8, pady=8)
            tk.Label(total_row, text=f"${total_sched:,.2f}",
                     font=("Inter", 11, "bold"),
                     fg="white", bg=theme.ACCENT).pack(side="right", padx=8)

            # ── Job Efficiency Report ─────────────────────────────────────
            efficiency = sa.job_efficiency_report(all_events)
            if efficiency:
                tk.Label(inner, text="Job Efficiency", font=F_H2,
                         fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(20, 4))
                tk.Label(inner,
                         text="Ranked by effective hourly rate. Flags scheduling friction.",
                         font=F_SMALL, fg=theme.MUTED, bg=theme.BG).pack(anchor="w", pady=(0, 8))
                ec = card(inner)
                for rank, job_eff in enumerate(efficiency, 1):
                    row = tk.Frame(ec, bg=theme.SIDEBAR,
                                   highlightbackground=theme.BORDER, highlightthickness=1)
                    row.pack(fill="x", pady=1)
                    medal = ["[1st]", "[2nd]", "[3rd]"][rank - 1] if rank <= 3 else f"#{rank}"
                    tk.Label(row, text=f"{medal}  {job_eff.name}",
                             font=("Inter", 10, "bold"),
                             fg=theme.TEXT, bg=theme.SIDEBAR,
                             width=22, anchor="w").pack(side="left", padx=8, pady=6)
                    tk.Label(row, text=f"${job_eff.income_per_hour:.2f}/hr",
                             font=("Inter", 10, "bold"), fg=theme.ACCENT,
                             bg=theme.SIDEBAR, width=12).pack(side="left")
                    tk.Label(row, text=job_eff.efficiency_note,
                             font=F_SMALL, fg=theme.MUTED,
                             bg=theme.SIDEBAR, wraplength=340,
                             justify="left").pack(side="left", padx=6)

        # ── Fallback: basic job list from FinancialState ──────────────────
        elif state.jobs:
            tk.Label(inner,
                     text="No scheduled shifts found. Showing jobs from your Data page.",
                     font=F_SMALL, fg=theme.MUTED, bg=theme.BG).pack(anchor="w", pady=(0, 10))
            c = card(inner)
            hdr = tk.Frame(c, bg=theme.ACCENT)
            hdr.pack(fill="x")
            for txt, w in [("Job", 22), ("Amount / Frequency", 20), ("Weekly Equiv.", 14)]:
                tk.Label(hdr, text=txt, font=("Inter", 10, "bold"), fg="white",
                         bg=theme.ACCENT, width=w, anchor="w").pack(side="left", padx=8, pady=5)
            total_income = state.total_income_per_week()
            for job in state.jobs:
                row    = tk.Frame(c, bg=theme.SIDEBAR,
                                  highlightbackground=theme.BORDER, highlightthickness=1)
                row.pack(fill="x", pady=1)
                weekly = job.weekly_income()
                pct    = (weekly / total_income * 100) if total_income else 0
                tk.Label(row, text=job.name, font=("Inter", 10, "bold"),
                         fg=theme.TEXT, bg=theme.SIDEBAR,
                         width=22, anchor="w").pack(side="left", padx=8, pady=6)
                tk.Label(row, text=f"${job.amount:.2f}/{job.frequency}",
                         font=F_SMALL, fg=theme.MUTED, bg=theme.SIDEBAR, width=20).pack(side="left")
                tk.Label(row, text=f"${weekly:,.2f}/wk  ({pct:.0f}%)",
                         font=("Inter", 10, "bold"), fg=theme.ACCENT,
                         bg=theme.SIDEBAR, width=18).pack(side="left")
            total_row = tk.Frame(c, bg=theme.ACCENT_L)
            total_row.pack(fill="x", pady=(2, 0))
            tk.Label(total_row, text="Total Weekly Income", font=("Inter", 11, "bold"),
                     fg=theme.ACCENT, bg=theme.ACCENT_L,
                     width=22, anchor="w").pack(side="left", padx=8, pady=8)
            tk.Label(total_row, text=f"${total_income:,.2f}",
                     font=("Inter", 11, "bold"),
                     fg=theme.ACCENT, bg=theme.ACCENT_L).pack(side="right", padx=8)
        else:
            tk.Label(inner,
                     text="No jobs or scheduled shifts found. Add shifts on the Schedule page.",
                     font=F_BODY, fg=theme.MUTED, bg=theme.BG).pack(anchor="w")

    # ── Categories ────────────────────────────────────────────────────────
    def _categories(self):
        state = self._app.state
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        tk.Label(inner, text="Expense Categories", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 12))
        breakdown = state.expense_by_category()
        if not breakdown:
            tk.Label(inner, text="No expenses on file. Add expenses to see the breakdown.",
                     font=F_BODY, fg=theme.MUTED, bg=theme.BG).pack(anchor="w")
            return

        total = sum(breakdown.values())
        c     = card(inner)
        for cat, amt in sorted(breakdown.items(), key=lambda x: x[1], reverse=True):
            pct = (amt / total * 100) if total else 0
            row = tk.Frame(c, bg=theme.SIDEBAR)
            row.pack(fill="x", padx=16, pady=6)
            tk.Label(row, text=cat, font=F_BODY,
                     fg=theme.TEXT, bg=theme.SIDEBAR, width=22, anchor="w").pack(side="left")
            tk.Label(row, text=f"${amt:.2f}/wk", font=("Inter", 11, "bold"),
                     fg=theme.TEXT, bg=theme.SIDEBAR, width=14).pack(side="left")
            tk.Label(row, text=f"{pct:.0f}%", font=F_SMALL,
                     fg=theme.MUTED, bg=theme.SIDEBAR).pack(side="left")

        tk.Label(inner, text="Pie Chart", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(16, 6))
        charts.render_category_pie(inner, breakdown)

    # ── Trends ────────────────────────────────────────────────────────────
    def _trends(self):
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        tk.Label(inner, text="Historical Trends", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 8))

        history = db.load_history()
        if len(history) < 2:
            tk.Label(inner,
                     text="Not enough history yet. Open the app on different days "
                          "and your trend chart will appear here.",
                     font=F_BODY, fg=theme.MUTED, bg=theme.BG,
                     wraplength=600, justify="left").pack(anchor="w")
        else:
            charts.render_trends_chart(inner, history)

        # ── Daily income from schedule (always shown if data exists) ──────
        all_events  = db.get_events()
        daily       = sa.daily_totals(all_events)
        top_days    = sa.top_earning_days(all_events, n=5)

        if daily:
            tk.Label(inner, text="Daily Income from Shifts", font=F_H2,
                     fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(20, 4))
            tk.Label(inner,
                     text="Income earned per day based on your scheduled shifts.",
                     font=F_SMALL, fg=theme.MUTED, bg=theme.BG).pack(anchor="w", pady=(0, 8))

            # Top earning days
            if top_days:
                tk.Label(inner, text="Top Earning Days", font=("Inter", 11, "bold"),
                         fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(4, 4))
                tc = card(inner, pady=4)
                for rank, (date_str, amt) in enumerate(top_days, 1):
                    row = tk.Frame(tc, bg=theme.SIDEBAR)
                    row.pack(fill="x", padx=16, pady=3)
                    tk.Label(row, text=f"#{rank}  {date_str}",
                             font=F_BODY, fg=theme.TEXT,
                             bg=theme.SIDEBAR, width=20, anchor="w").pack(side="left")
                    tk.Label(row, text=f"${amt:,.2f}",
                             font=("Inter", 11, "bold"), fg=theme.ACCENT,
                             bg=theme.SIDEBAR).pack(side="left", padx=12)

        # ── Snapshot table ────────────────────────────────────────────────
        if len(history) >= 1:
            tk.Label(inner, text="Snapshot History", font=F_H2,
                     fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(16, 6))
            hdr = tk.Frame(inner, bg=theme.ACCENT)
            hdr.pack(fill="x")
            for txt, w in [("Date", 14), ("Balance", 12), ("Income/wk", 12),
                           ("Expenses/wk", 14), ("Net/wk", 12)]:
                tk.Label(hdr, text=txt, font=("Inter", 9, "bold"), fg="white",
                         bg=theme.ACCENT, width=w, anchor="w").pack(side="left", padx=6, pady=4)

            for i, h in enumerate(reversed(history)):
                bg_row    = theme.SIDEBAR if i % 2 == 0 else theme.ACCENT_L
                row       = tk.Frame(inner, bg=bg_row)
                row.pack(fill="x")
                net_color = theme.ACCENT if h["net"] >= 0 else theme.DANGER
                for val, w in [
                    (h["date"],               14),
                    (f"${h['balance']:,.2f}", 12),
                    (f"${h['income']:,.2f}",  12),
                    (f"${h['expenses']:,.2f}", 14),
                    (f"${h['net']:+,.2f}",    12),
                ]:
                    fg = net_color if "+," in val or "-" in val[:2] else theme.TEXT
                    tk.Label(row, text=val, font=("Inter", 9),
                             fg=fg, bg=bg_row, width=w, anchor="w").pack(side="left", padx=6, pady=3)
