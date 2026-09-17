"""
insight_engine.py — Explains financial scores in plain English.

InsightEngine does NOT calculate scores — it reads them from FinancialState.
All score logic lives in FinancialState.
"""
from __future__ import annotations

from backend.core.config import RISK_VERY_STABLE, RISK_STABLE, RISK_MODERATE
from backend.core.config import EXPENSE_RATIO_HIGH, EXPENSE_RATIO_WARNING


class InsightEngine:

    # ── Score labels ──────────────────────────────────────────────────────────

    def risk_label(self, score: int) -> str:
        """Plain-English label for a risk score."""
        if   score >= RISK_VERY_STABLE: return "Very Stable"
        elif score >= RISK_STABLE:      return "Stable"
        elif score >= RISK_MODERATE:    return "Moderate Risk"
        else:                           return "High Risk"

    def health_label(self, score: int) -> str:
        """Plain-English label for a health score."""
        if   score >= 80: return "Excellent"
        elif score >= 60: return "Moderate"
        elif score >= 40: return "Weak"
        else:             return "Critical"

    # ── Delegating wrappers (so main.py can call insight_engine.risk_score) ───

    def risk_score(self, state: object) -> int:
        """Delegates to state.risk_score() — single source of truth."""
        return state.risk_score()  # type: ignore[union-attr]

    def financial_health_score(self, state: object) -> int:
        """Delegates to state.financial_health_score() — single source of truth."""
        return state.financial_health_score()  # type: ignore[union-attr]

    # ── Insights ──────────────────────────────────────────────────────────────

    def generate_insights(self, state: object, simulation_results: dict | None = None) -> list[str]:
        """
        Returns a list of plain-English insights about the user's finances.
        Reads all data from state — does not recalculate anything independently.
        """
        insights: list[str] = []
        net      = state.net_weekly_flow()
        savings  = state.savings_rate()
        income   = state.total_income_per_week()
        expenses = state.total_expense_per_week()

        # Weekly flow
        if net > 0:
            insights.append(f"You have a weekly surplus of ${net:.2f}.")
        elif net < 0:
            insights.append(
                f"You are running a weekly deficit of ${abs(net):.2f}. "
                f"Reduce expenses or add income."
            )
        else:
            insights.append("You are exactly breaking even each week.")

        # Savings rate
        if savings >= 0.20:
            insights.append(f"Strong savings rate of {savings*100:.1f}%.")
        elif savings >= 0.10:
            insights.append(
                f"Savings rate of {savings*100:.1f}% is acceptable but could be higher."
            )
        elif savings > 0:
            insights.append(
                f"Savings rate of {savings*100:.1f}% is low. Aim for at least 10–20%."
            )
        elif savings < 0:
            insights.append("Negative savings rate — you are spending more than you earn.")

        # Expense ratio
        if income > 0:
            ratio = expenses / income
            if ratio > EXPENSE_RATIO_HIGH:
                insights.append(
                    "Expenses consume over 90% of your income. High financial pressure."
                )
            elif ratio > EXPENSE_RATIO_WARNING:
                insights.append(
                    "Expenses are 70–90% of your income. Limited room for savings."
                )

        # Top expense category (uses weekly_amount via expense_by_category)
        breakdown = state.expense_by_category()
        if breakdown:
            top = max(breakdown, key=breakdown.get)
            insights.append(
                f"Largest expense category: {top} (${breakdown[top]:.2f}/week)."
            )

        # Monte Carlo result (optional)
        if simulation_results:
            dp = simulation_results["deficit_probability"]
            if dp == 0:
                insights.append("Simulation shows no risk of running out of money.")
            elif dp < 10:
                insights.append(f"Low deficit risk: {dp}% chance of running out of money.")
            elif dp < 30:
                insights.append(
                    f"Moderate deficit risk: {dp}% chance of running out of money."
                )
            else:
                insights.append(
                    f"High deficit risk: {dp}% chance of running out of money. Take action."
                )

        return insights
