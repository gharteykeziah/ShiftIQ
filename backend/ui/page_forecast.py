"""page_forecast.py — Forecasting page (projection, scenarios, Monte Carlo)."""
import tkinter as tk

import backend.ui.theme as theme
import backend.core.charts as charts
from backend.ui.theme import F_BODY, F_SMALL, F_H2
from backend.core.widgets import (ScrollFrame, TabBar, page_title, card, kv_row,
                     labeled_entry, action_btn, status_lbl, section_divider)
from backend.core.scenario_engine import Scenario
from backend.core.simulation import simulate_whatif, run_monte_carlo
from backend.core.config import PROJECTION_WEEKS


class ForecastingPage(tk.Frame):
    """Forecasting page: balance projections, scenario comparison, what-if, and Monte Carlo."""
    def __init__(self, parent, app):
        """Set up tab bar and body frame; activate the Projection tab."""
        super().__init__(parent, bg=theme.BG)
        self._app = app

        header = tk.Frame(self, bg=theme.BG, padx=36, pady=16)
        header.pack(fill="x")
        page_title(header, "Forecasting",
                   "Project your balance, compare scenarios, and simulate life events.")

        tb = TabBar(self, [
            ("projection", "Projection"),
            ("scenarios",  "Scenarios"),
            ("simulation", "Simulation"),
        ])
        tb.pack(fill="x", padx=36)
        self._body = tk.Frame(self, bg=theme.BG)
        self._body.pack(fill="both", expand=True)
        tb.bind_select(self._render)
        tb.activate("projection")

    def _render(self, key):
        """Destroy and rebuild the body frame for the selected tab key."""
        for w in self._body.winfo_children():
            w.destroy()
        {"projection": self._projection,
         "scenarios":  self._scenarios,
         "simulation": self._simulation}[key]()

    # ── Projection ────────────────────────────────────────────────────────
    def _projection(self):
        """Render the Projection tab — balance at 4, 8, 12, 26, 52-week horizons."""
        state = self._app.state
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        tk.Label(inner, text="Balance Projection", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 8))

        auto = card(inner)
        tk.Label(auto, text="Automatic projections at common horizons",
                 font=F_SMALL, fg=theme.MUTED, bg=theme.SIDEBAR,
                 padx=16, pady=8).pack(anchor="w")
        for wks in PROJECTION_WEEKS:
            projected = state.project_balance(wks)
            color = theme.ACCENT if projected >= 0 else theme.DANGER
            kv_row(auto, f"In {wks} weeks", f"${projected:,.2f}", color)

        section_divider(inner)
        tk.Label(inner, text="Balance Over Time", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 8))
        charts.render_projection_chart(inner, state)

        section_divider(inner)
        tk.Label(inner, text="Custom Projection", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 8))
        weeks_e = labeled_entry(inner, "Number of weeks", width=10)
        result  = tk.Frame(inner, bg=theme.BG)
        result.pack(anchor="w")

        def project():
            for w in result.winfo_children():
                w.destroy()
            try:
                weeks = _pi(weeks_e, "Weeks")
                if weeks <= 0:
                    raise ValueError("Weeks must be greater than zero.")
                projected = state.project_balance(weeks)
                color = theme.ACCENT if projected >= 0 else theme.DANGER
                tk.Label(result,
                         text=f"In {weeks} weeks:  ${projected:,.2f}",
                         font=("Inter", 12, "bold"), fg=color, bg=theme.BG).pack(anchor="w", pady=8)
            except ValueError as e:
                status_lbl(result, str(e), False)

        action_btn(inner, "Project", project)

    # ── Scenarios ─────────────────────────────────────────────────────────
    def _scenarios(self):
        """Render the Scenarios tab — side-by-side comparison of income changes."""
        state          = self._app.state
        scenario_engine = self._app.scenario_engine
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        tk.Label(inner, text="Compare Scenarios", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 8))
        tk.Label(inner,
                 text="Compare two paths against your current situation. "
                      "Define Scenario A and B, then see all three projections side by side.",
                 font=F_SMALL, fg=theme.MUTED, bg=theme.BG,
                 wraplength=680, justify="left").pack(anchor="w", pady=(0, 10))

        weeks_e = labeled_entry(inner, "Forecast Weeks", width=10)

        tk.Label(inner, text="Scenario A", font=F_H2,
                 fg=theme.ACCENT, bg=theme.BG).pack(anchor="w", pady=(14, 0))
        a_name_e  = labeled_entry(inner, "Name  (e.g. Side hustle)")
        a_extra_e = labeled_entry(inner, "Extra income per week ($)  (0 if none)", width=10)
        a_raise_e = labeled_entry(inner, "Raise as decimal  (0.1 = 10%,  0 if none)", width=10)

        tk.Label(inner, text="Scenario B", font=F_H2,
                 fg=theme.BLUE, bg=theme.BG).pack(anchor="w", pady=(14, 0))
        b_name_e  = labeled_entry(inner, "Name  (e.g. Cut expenses)")
        b_extra_e = labeled_entry(inner, "Extra income per week ($)  (0 if none)", width=10)
        b_raise_e = labeled_entry(inner, "Raise as decimal  (0.1 = 10%,  0 if none)", width=10)

        result_frame = tk.Frame(inner, bg=theme.BG)
        result_frame.pack(fill="x", pady=12)

        def compare():
            for w in result_frame.winfo_children():
                w.destroy()
            try:
                weeks = _pi(weeks_e, "Weeks")
                if weeks <= 0:
                    raise ValueError("Weeks must be greater than zero.")
                scenarios = [
                    Scenario(a_name_e.get().strip() or "Scenario A",
                             float(a_extra_e.get() or 0),
                             float(a_raise_e.get() or 0)),
                    Scenario(b_name_e.get().strip() or "Scenario B",
                             float(b_extra_e.get() or 0),
                             float(b_raise_e.get() or 0)),
                ]
                results = scenario_engine.compare_scenarios(state, weeks, scenarios)

                current_balance = state.project_balance(weeks)
                all_rows = [
                    {"name": "Current (no change)",
                     "projected_balance": current_balance,
                     "net_weekly_flow":   state.net_weekly_flow(),
                     "color": theme.MUTED},
                ] + [dict(r, color=c) for r, c in zip(results, [theme.ACCENT, theme.BLUE])]

                hdr = tk.Frame(result_frame, bg=theme.ACCENT)
                hdr.pack(fill="x")
                for txt, w in [("Scenario", 28), (f"{weeks}-Week Balance", 18), ("Weekly Flow", 14)]:
                    tk.Label(hdr, text=txt, font=("Inter", 10, "bold"), fg="white",
                             bg=theme.ACCENT, width=w, anchor="w").pack(side="left", padx=8, pady=5)

                for row in all_rows:
                    r = tk.Frame(result_frame, bg=theme.SIDEBAR,
                                 highlightbackground=theme.BORDER, highlightthickness=1)
                    r.pack(fill="x", pady=1)
                    tk.Label(r, text=row["name"], font=("Inter", 11, "bold"),
                             fg=row["color"], bg=theme.SIDEBAR,
                             width=28, anchor="w").pack(side="left", padx=8, pady=8)
                    tk.Label(r, text=f"${row['projected_balance']:,.2f}",
                             font=("Inter", 11, "bold"),
                             fg=row["color"], bg=theme.SIDEBAR, width=18).pack(side="left")
                    tk.Label(r, text=f"${row['net_weekly_flow']:+,.2f}/wk",
                             font=F_SMALL, fg=theme.MUTED, bg=theme.SIDEBAR,
                             width=14).pack(side="left")
            except ValueError as e:
                status_lbl(result_frame, str(e), False)

        action_btn(inner, "Compare Scenarios", compare)

    # ── Simulation ────────────────────────────────────────────────────────
    def _simulation(self):
        """Render the Simulation tab — what-if and Monte Carlo tools."""
        state = self._app.state
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        # ── What-If ─────────────────────────────────────────────────────
        tk.Label(inner, text="What-If Simulator", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 4))
        tk.Label(inner,
                 text="Describe something that happened or could happen, enter the dollar impact "
                      "(negative = costs you money), and see how your balance plays out week by week.",
                 font=F_SMALL, fg=theme.MUTED, bg=theme.BG,
                 wraplength=680, justify="left").pack(anchor="w", pady=(0, 8))

        tk.Label(inner,
                 text='What happened?  e.g. "Got sick"  /  "Picked up a shift"  /  "Car broke down"',
                 font=F_BODY, fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(8, 2))
        desc_e = tk.Entry(inner, font=F_BODY, width=46, relief="flat",
                          highlightbackground=theme.BORDER, highlightthickness=1,
                          bg=theme.SIDEBAR, fg=theme.TEXT, insertbackground=theme.TEXT)
        desc_e.pack(anchor="w", ipady=5)

        tk.Label(inner, text="Dollar impact  (+80 = earned $80   |   -90 = lost $90)",
                 font=F_SMALL, fg=theme.MUTED, bg=theme.BG).pack(anchor="w", pady=(10, 2))
        amount_e = tk.Entry(inner, font=F_BODY, width=14, relief="flat",
                            highlightbackground=theme.BORDER, highlightthickness=1,
                            bg=theme.SIDEBAR, fg=theme.TEXT, insertbackground=theme.TEXT)
        amount_e.pack(anchor="w", ipady=5)

        tk.Label(inner, text="How many weeks to simulate?",
                 font=F_BODY, fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(10, 2))
        weeks_wi_e = tk.Entry(inner, font=F_BODY, width=8, relief="flat",
                              highlightbackground=theme.BORDER, highlightthickness=1,
                              bg=theme.SIDEBAR, fg=theme.TEXT, insertbackground=theme.TEXT)
        weeks_wi_e.pack(anchor="w", ipady=5)

        wi_result = tk.Frame(inner, bg=theme.BG)
        wi_result.pack(fill="x", pady=10)

        def run_whatif():
            for w in wi_result.winfo_children():
                w.destroy()
            try:
                desc          = desc_e.get().strip() or "This event"
                dollar_change = _pf(amount_e, "Dollar impact")
                weeks         = _pi(weeks_wi_e, "Weeks")
                if weeks <= 0:
                    raise ValueError("Weeks must be greater than zero.")
                result    = simulate_whatif(state, desc, dollar_change, weeks)
                direction = (f"+${abs(dollar_change):.2f}" if dollar_change >= 0
                             else f"-${abs(dollar_change):.2f}")
                tk.Label(wi_result,
                         text=f'"{desc}"  ({direction})',
                         font=("Inter", 12, "bold"), fg=theme.TEXT, bg=theme.BG,
                         ).pack(anchor="w", pady=(4, 8))

                hdr = tk.Frame(wi_result, bg=theme.ACCENT)
                hdr.pack(fill="x")
                for txt, w in [("Week", 7), ("Balance", 13), ("What happened", 45)]:
                    tk.Label(hdr, text=txt, font=("Inter", 10, "bold"),
                             fg="white", bg=theme.ACCENT, width=w,
                             anchor="w").pack(side="left", padx=8, pady=5)

                for entry in result["history"]:
                    b_color = theme.ACCENT if entry["balance"] >= 0 else theme.DANGER
                    row = tk.Frame(wi_result, bg=theme.SIDEBAR,
                                   highlightbackground=theme.BORDER, highlightthickness=1)
                    row.pack(fill="x", pady=1)
                    tk.Label(row, text=f"Wk {entry['week']}", font=F_SMALL,
                             fg=theme.MUTED, bg=theme.SIDEBAR, width=7).pack(side="left", padx=8, pady=6)
                    tk.Label(row, text=f"${entry['balance']:,.2f}",
                             font=("Inter", 10, "bold"), fg=b_color,
                             bg=theme.SIDEBAR, width=13).pack(side="left")
                    tk.Label(row, text=entry["note"], font=F_SMALL,
                             fg=theme.TEXT, bg=theme.SIDEBAR,
                             wraplength=380, justify="left").pack(side="left", padx=8)

                tk.Label(wi_result, text=result["summary"],
                         font=("Inter", 10, "italic"), fg=theme.MUTED, bg=theme.BG,
                         wraplength=660, justify="left").pack(anchor="w", pady=(10, 0))
            except ValueError as e:
                status_lbl(wi_result, str(e), False)

        action_btn(inner, "Simulate This", run_whatif)

        # ── Monte Carlo ──────────────────────────────────────────────────
        section_divider(inner)
        tk.Label(inner, text="500 Possible Futures  (Monte Carlo)", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 4))
        tk.Label(inner,
                 text="We run 500 different versions of your next N weeks — each with random life events "
                      "(extra shifts, car repairs, medical bills, etc.). You get the most likely outcome, "
                      "best/worst cases, and the probability of running out of money.",
                 font=F_SMALL, fg=theme.MUTED, bg=theme.BG,
                 wraplength=680, justify="left").pack(anchor="w", pady=(0, 8))

        weeks_mc_e = labeled_entry(inner, "How many weeks ahead?", width=8)
        mc_result  = tk.Frame(inner, bg=theme.BG)
        mc_result.pack(fill="x", pady=10)

        def run_mc():
            for w in mc_result.winfo_children():
                w.destroy()
            try:
                weeks = _pi(weeks_mc_e, "Weeks")
                if weeks <= 0:
                    raise ValueError("Weeks must be greater than zero.")
                r = run_monte_carlo(state, weeks)
                tk.Label(mc_result, text=r["plain_summary"],
                         font=F_BODY, fg=theme.TEXT, bg=theme.BG,
                         wraplength=680, justify="left").pack(anchor="w", pady=(0, 10))
                rc = card(mc_result)
                for key, val, vc in [
                    ("Most likely outcome",  f"${r['average']:,.2f}",        theme.TEXT),
                    ("Median outcome",       f"${r['median']:,.2f}",         theme.TEXT),
                    ("25th percentile",      f"${r['p25']:,.2f}",            theme.DANGER),
                    ("75th percentile",      f"${r['p75']:,.2f}",            theme.ACCENT),
                    ("Best case",            f"${r['best_case']:,.2f}",      theme.ACCENT),
                    ("Worst case",           f"${r['worst_case']:,.2f}",     theme.DANGER),
                    ("Chance you run out",   f"{r['deficit_probability']}%",
                     theme.DANGER if r["deficit_probability"] > 20 else theme.TEXT),
                    ("Chance you stay safe", f"{r['safe_probability']}%",    theme.ACCENT),
                ]:
                    kv_row(rc, key, val, vc)
                charts.render_mc_histogram(mc_result, r["ending_balances"], weeks)
            except ValueError as e:
                status_lbl(mc_result, str(e), False)

        action_btn(inner, "Run 500 Futures", run_mc, color=theme.BLUE)


# ── Private helpers ───────────────────────────────────────────────────────────
def _pf(entry, name) -> float:
    raw = entry.get().strip()
    if not raw:
        raise ValueError(f"{name} cannot be empty.")
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{name}: please enter a valid number (e.g. 12.50).")


def _pi(entry, name) -> int:
    raw = entry.get().strip()
    if not raw:
        raise ValueError(f"{name} cannot be empty.")
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"{name}: please enter a whole number (e.g. 4).")
