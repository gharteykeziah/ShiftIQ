"""
scenario_engine.py — Financial scenario projections.

Bug fix: extra_weekly is added once to total weekly income, NOT once per job.
         A user with 3 jobs and extra_weekly=50 gets +$50/week, not +$150/week.
"""
from __future__ import annotations


class Scenario:
    def __init__(self, name: str, extra_weekly: float = 0.0, raise_percent: float = 0.0) -> None:
        self.name          = name
        self.extra_weekly  = extra_weekly   # extra $ per week added on top (once)
        self.raise_percent = raise_percent  # % raise applied to total base income


class ScenarioEngine:

    def project_balance(self, state, weeks: int, scenario: Scenario | None = None) -> float:
        """Return the projected balance after *weeks* weeks under *scenario*."""
        extra_weekly  = scenario.extra_weekly  if scenario else 0.0
        raise_percent = scenario.raise_percent if scenario else 0.0

        base_income     = state.total_income_per_week()
        weekly_income   = base_income * (1 + raise_percent) + extra_weekly
        weekly_expenses = state.total_expense_per_week()
        net             = weekly_income - weekly_expenses

        return round(state.current_balance() + net * weeks, 2)

    def compare_scenarios(
        self,
        state,
        weeks: int,
        scenarios: list[Scenario],
    ) -> list[dict[str, object]]:
        """Return scenarios sorted by projected balance (highest first)."""
        results: list[dict[str, object]] = []
        for scenario in scenarios:
            balance       = self.project_balance(state, weeks, scenario)
            base_income   = state.total_income_per_week()
            weekly_income = base_income * (1 + scenario.raise_percent) + scenario.extra_weekly
            net           = weekly_income - state.total_expense_per_week()
            results.append({
                "name":              scenario.name,
                "projected_balance": balance,
                "net_weekly_flow":   round(net, 2)
            })

        results.sort(key=lambda r: r["projected_balance"], reverse=True)  # type: ignore[arg-type]
        return results
