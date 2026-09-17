"""page_dashboard.py — Dashboard page."""
import tkinter as tk

import backend.ui.theme as theme
from backend.ui.theme import F_BODY, F_SMALL, F_H2, F_NUM
from backend.core.widgets import ScrollFrame, page_title, card, kv_row


class DashboardPage(tk.Frame):
    """One-screen financial snapshot: balance, net flow, risk/health scores, and top insights."""
    def __init__(self, parent, app):
        """Build and render the dashboard using the app's current state."""
        super().__init__(parent, bg=theme.BG)
        self._app = app

        sf    = ScrollFrame(self)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=28)

        state          = app.state
        insight_engine = app.insight_engine
        risk   = insight_engine.risk_score(state)
        health = insight_engine.financial_health_score(state)

        page_title(inner, "Dashboard", "Your financial snapshot at a glance.")

        # ── Balance hero card ─────────────────────────────────────────────
        hero = tk.Frame(inner, bg=theme.ACCENT, pady=20, padx=24)
        hero.pack(fill="x", pady=(0, 16))
        tk.Label(hero, text="Current Balance",
                 font=F_SMALL, fg="#b2d8c8", bg=theme.ACCENT).pack(anchor="w")
        tk.Label(hero, text=f"${state.current_balance():,.2f}",
                 font=F_NUM, fg="white", bg=theme.ACCENT).pack(anchor="w")
        tk.Label(hero,
                 text=f"Net weekly flow:  ${state.net_weekly_flow():+.2f}  •  "
                      f"Savings rate: {state.savings_rate()*100:.1f}%",
                 font=F_SMALL, fg="#b2d8c8", bg=theme.ACCENT).pack(anchor="w", pady=(4, 0))

        # ── Stats card ───────────────────────────────────────────────────
        stats   = card(inner)
        r_color = theme.ACCENT if risk   >= 60 else ("#e67e22" if risk   >= 40 else theme.DANGER)
        h_color = theme.ACCENT if health >= 60 else ("#e67e22" if health >= 40 else theme.DANGER)
        for key, val, vc in [
            ("Weekly Income",   f"${state.total_income_per_week():,.2f}",  theme.TEXT),
            ("Weekly Expenses", f"${state.total_expense_per_week():,.2f}", theme.TEXT),
            ("Risk Score",   f"{risk}/100  —  {insight_engine.risk_label(risk)}",     r_color),
            ("Health Score", f"{health}/100  —  {insight_engine.health_label(health)}", h_color),
        ]:
            kv_row(stats, key, val, vc)

        # ── Quick insights ────────────────────────────────────────────────
        tk.Label(inner, text="Quick Insights", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(18, 6))
        insights = insight_engine.generate_insights(state)[:3]
        if insights:
            ic = card(inner)
            for txt in insights:
                tk.Label(ic, text=f"• {txt}", font=F_BODY,
                         fg=theme.TEXT, bg=theme.SIDEBAR,
                         wraplength=700, justify="left",
                         padx=16, pady=6).pack(anchor="w")
        else:
            tk.Label(inner, text="Add jobs and expenses to see insights.",
                     font=F_BODY, fg=theme.MUTED, bg=theme.BG).pack(anchor="w")
