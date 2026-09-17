"""
test_shiftiq.py — Automated test suite for ShiftIQ.

Run with:
    python3 -m pytest test_shiftiq.py -v

All tests are self-contained. The database tests use a temporary file —
nothing is written to the real finance.db during testing.
"""

import os
import sys
import pytest

# Make sure we import from the project folder
sys.path.insert(0, os.path.dirname(__file__))

from backend.core.model import Job, Expense, FREQ_TO_WEEKLY, FREQUENCIES
from backend.core.insight_engine import InsightEngine
from backend.core.scenario_engine import ScenarioEngine, Scenario
from backend.core.simulation import simulate_whatif, run_monte_carlo
import backend.core.database as database
import backend.core.db_connection as db_connection


# ─────────────────────────────────────────────────────────────────────────────
#  FAKE STATE  (mirrors FinancialState's public API — no database required)
# ─────────────────────────────────────────────────────────────────────────────

class FakeState:
    """Drop-in replacement for FinancialState for testing calculations only."""

    def __init__(self, jobs=None, expenses=None, balance=0.0):
        self.jobs     = jobs     or []
        self.expenses = expenses or []
        self.balance  = balance

    def current_balance(self):
        return self.balance

    def total_income_per_week(self):
        return sum(j.weekly_income() for j in self.jobs)

    def total_expense_per_week(self):
        return sum(e.weekly_amount() for e in self.expenses)

    def net_weekly_flow(self):
        return self.total_income_per_week() - self.total_expense_per_week()

    def savings_rate(self):
        inc = self.total_income_per_week()
        return self.net_weekly_flow() / inc if inc else 0.0

    def expense_by_category(self):
        out = {}
        for e in self.expenses:
            out[e.category] = out.get(e.category, 0.0) + e.weekly_amount()
        return out

    def projected_income(self, weeks, scenario=None):
        scenario      = scenario or {}
        raise_percent = scenario.get("raise_percent", 0.0)
        extra_weekly  = scenario.get("extra_weekly",  0.0)
        base          = self.total_income_per_week()
        return (base * (1 + raise_percent) + extra_weekly) * weeks

    def projected_expenses(self, weeks):
        return self.total_expense_per_week() * weeks

    def project_balance(self, weeks, scenario=None):
        return self.balance + self.projected_income(weeks, scenario) - self.projected_expenses(weeks)

    def weeks_to_goal(self, goal):
        if self.net_weekly_flow() <= 0:
            return None
        bal, wks = self.balance, 0
        while bal < goal:
            bal += self.net_weekly_flow()
            wks += 1
            if wks > 10_000:
                return None
        return wks

    def goal_progress(self, goal):
        return (self.balance / goal * 100) if goal else None

    def financial_health_score(self):
        from backend.core.config import SAVINGS_STRONG, SAVINGS_GOOD, SAVINGS_OK
        s = self.savings_rate()
        if   s >= SAVINGS_STRONG: return 90
        elif s >= SAVINGS_GOOD:   return 75
        elif s >= SAVINGS_OK:     return 60
        elif s >= 0:              return 50
        else:                     return 20

    def risk_score(self):
        from backend.core.config import SAVINGS_GOOD, SAVINGS_OK
        income   = self.total_income_per_week()
        expenses = self.total_expense_per_week()
        savings  = self.savings_rate()
        score    = 50
        if self.net_weekly_flow() < 0:              score -= 20
        if income > 0 and expenses / income > 0.8:  score -= 15
        if   savings >= SAVINGS_GOOD:               score += 20
        elif savings >= SAVINGS_OK:                 score += 10
        elif savings < 0:                           score -= 25
        if self.current_balance() <= 0:             score -= 10
        return max(0, min(100, score))


# Standard state reused across many tests:
#   income  = $500/wk (one Weekly job)
#   expenses= $400/wk ($300 Housing Weekly + $100 Food Weekly)
#   net     = $100/wk  |  savings rate = 20%  |  balance = $1,000

@pytest.fixture
def base_state():
    return FakeState(
        jobs=[Job("Work", 500, "Weekly")],
        expenses=[
            Expense("Rent", 300, "Housing", "2024-01-01", "Weekly"),
            Expense("Food", 100, "Food",    "2024-01-01", "Weekly"),
        ],
        balance=1000.0,
    )


# ═════════════════════════════════════════════════════════════════════════════
#  1. MODEL — Job
# ═════════════════════════════════════════════════════════════════════════════

class TestJobModel:

    def test_weekly_frequency(self):
        assert Job("X", 100, "Weekly").weekly_income() == 100.0

    def test_daily_frequency(self):
        assert Job("X", 100, "Daily").weekly_income() == 700.0

    def test_biweekly_frequency(self):
        assert Job("X", 100, "Biweekly").weekly_income() == 50.0

    def test_monthly_frequency(self):
        assert abs(Job("X", 100, "Monthly").weekly_income() - 100 * 12 / 52) < 0.001

    def test_unknown_frequency_falls_back_to_weekly(self):
        assert Job("X", 100, "Quarterly").weekly_income() == 100.0

    def test_to_dict(self):
        d = Job("Barista", 300, "Biweekly").to_dict()
        assert d == {"name": "Barista", "amount": 300, "frequency": "Biweekly"}

    def test_from_dict_roundtrip(self):
        j = Job("Barista", 300, "Biweekly")
        j2 = Job.from_dict(j.to_dict())
        assert j2.name == "Barista"
        assert j2.amount == 300
        assert j2.frequency == "Biweekly"

    def test_from_dict_defaults_frequency_to_weekly(self):
        j = Job.from_dict({"name": "X", "amount": 50})
        assert j.frequency == "Weekly"

    def test_repr_contains_name(self):
        assert "Barista" in repr(Job("Barista", 200, "Weekly"))


# ═════════════════════════════════════════════════════════════════════════════
#  2. MODEL — Expense
# ═════════════════════════════════════════════════════════════════════════════

class TestExpenseModel:

    def test_weekly_frequency(self):
        assert Expense("Rent", 400, "Housing", "2024-01-01", "Weekly").weekly_amount() == 400.0

    def test_daily_frequency(self):
        assert Expense("Coffee", 5, "Food", "2024-01-01", "Daily").weekly_amount() == 35.0

    def test_biweekly_frequency(self):
        assert Expense("Bus pass", 60, "Transport", "2024-01-01", "Biweekly").weekly_amount() == 30.0

    def test_monthly_frequency(self):
        assert abs(Expense("Rent", 1200, "Housing", "2024-01-01", "Monthly").weekly_amount() - 1200 * 12 / 52) < 0.001

    def test_default_frequency_is_monthly(self):
        assert Expense("Rent", 1000, "Housing", "2024-01-01").frequency == "Monthly"

    def test_to_dict(self):
        d = Expense("Rent", 1000, "Housing", "2024-01-01", "Monthly").to_dict()
        assert d["name"] == "Rent"
        assert d["frequency"] == "Monthly"

    def test_from_dict_roundtrip(self):
        e  = Expense("Phone", 30, "Bills", "2024-06-01", "Monthly")
        e2 = Expense.from_dict(e.to_dict())
        assert e2.name == "Phone"
        assert e2.category == "Bills"
        assert e2.frequency == "Monthly"

    def test_from_dict_defaults_frequency_to_monthly(self):
        e = Expense.from_dict({"name": "X", "amount": 50, "category": "Bills", "date": "2024-01-01"})
        assert e.frequency == "Monthly"


# ═════════════════════════════════════════════════════════════════════════════
#  3. FREQUENCY CONSTANTS
# ═════════════════════════════════════════════════════════════════════════════

class TestFrequencyConstants:

    def test_all_four_frequencies_in_list(self):
        for f in ["Daily", "Weekly", "Biweekly", "Monthly"]:
            assert f in FREQUENCIES

    def test_all_four_frequencies_in_lookup(self):
        for f in ["Daily", "Weekly", "Biweekly", "Monthly"]:
            assert f in FREQ_TO_WEEKLY

    def test_weekly_is_1(self):
        assert FREQ_TO_WEEKLY["Weekly"] == 1.0

    def test_daily_is_7(self):
        assert FREQ_TO_WEEKLY["Daily"] == 7.0

    def test_biweekly_is_half(self):
        assert FREQ_TO_WEEKLY["Biweekly"] == 0.5

    def test_monthly_less_than_weekly(self):
        assert FREQ_TO_WEEKLY["Monthly"] < 1.0


# ═════════════════════════════════════════════════════════════════════════════
#  4. WEEKLY TOTALS
# ═════════════════════════════════════════════════════════════════════════════

class TestWeeklyTotals:

    def test_income_single_job(self, base_state):
        assert base_state.total_income_per_week() == 500.0

    def test_income_two_jobs(self):
        state = FakeState(jobs=[
            Job("A", 200, "Weekly"),
            Job("B", 400, "Biweekly"),   # → $200/wk
        ])
        assert state.total_income_per_week() == 400.0

    def test_income_no_jobs(self):
        assert FakeState().total_income_per_week() == 0.0

    def test_expenses_all_weekly(self, base_state):
        assert base_state.total_expense_per_week() == 400.0

    def test_expenses_monthly_converted(self):
        state = FakeState(expenses=[
            Expense("Rent", 1200, "Housing", "2024-01-01", "Monthly"),
        ])
        assert abs(state.total_expense_per_week() - 1200 * 12 / 52) < 0.001

    def test_net_surplus(self, base_state):
        assert abs(base_state.net_weekly_flow() - 100.0) < 0.001

    def test_net_deficit(self):
        state = FakeState(
            jobs=[Job("Job", 200, "Weekly")],
            expenses=[Expense("E", 300, "Bills", "2024-01-01", "Weekly")],
        )
        assert abs(state.net_weekly_flow() - (-100.0)) < 0.001

    def test_savings_rate_20_percent(self, base_state):
        assert abs(base_state.savings_rate() - 0.20) < 0.0001

    def test_savings_rate_no_income(self):
        assert FakeState().savings_rate() == 0.0

    def test_savings_rate_negative(self):
        state = FakeState(
            jobs=[Job("Job", 100, "Weekly")],
            expenses=[Expense("E", 200, "Bills", "2024-01-01", "Weekly")],
        )
        assert state.savings_rate() < 0

    def test_expense_by_category_splits_correctly(self, base_state):
        bd = base_state.expense_by_category()
        assert abs(bd["Housing"] - 300.0) < 0.001
        assert abs(bd["Food"] - 100.0) < 0.001

    def test_expense_by_category_uses_weekly_amount(self):
        # Monthly expense must appear as monthly-converted-to-weekly, not raw amount
        state = FakeState(expenses=[
            Expense("Rent", 1000, "Housing", "2024-01-01", "Monthly"),
        ])
        bd = state.expense_by_category()
        assert abs(bd["Housing"] - 1000 * 12 / 52) < 0.001
        assert bd["Housing"] != 1000   # must NOT be the raw monthly amount

    def test_expense_by_category_aggregates_same_category(self):
        state = FakeState(expenses=[
            Expense("Rent",     600, "Housing", "2024-01-01", "Weekly"),
            Expense("Internet", 100, "Housing", "2024-01-01", "Weekly"),
        ])
        bd = state.expense_by_category()
        assert abs(bd["Housing"] - 700.0) < 0.001


# ═════════════════════════════════════════════════════════════════════════════
#  5. PROJECTIONS
# ═════════════════════════════════════════════════════════════════════════════

class TestProjections:

    def test_4_week_projection(self, base_state):
        # 1000 + 100 * 4 = 1400
        assert abs(base_state.project_balance(4) - 1400.0) < 0.001

    def test_zero_week_projection_equals_balance(self, base_state):
        assert abs(base_state.project_balance(0) - 1000.0) < 0.001

    def test_projection_with_raise(self, base_state):
        # 10% raise: income → 550, net → 150/wk → 1000 + 600 = 1600
        assert abs(base_state.project_balance(4, {"raise_percent": 0.1}) - 1600.0) < 0.001

    def test_projection_with_extra_weekly(self, base_state):
        # extra $50/wk: net → 150 → 1000 + 600 = 1600
        assert abs(base_state.project_balance(4, {"extra_weekly": 50}) - 1600.0) < 0.001

    def test_projection_negative_flow(self):
        state = FakeState(
            jobs=[Job("Job", 100, "Weekly")],
            expenses=[Expense("E", 200, "Bills", "2024-01-01", "Weekly")],
            balance=500.0,
        )
        # net = -100/wk → 500 - 400 = 100
        assert abs(state.project_balance(4) - 100.0) < 0.001

    def test_raise_percent_applies_once_not_per_job(self):
        # With two jobs, raise should be applied once to total base, not looped
        state = FakeState(
            jobs=[Job("A", 200, "Weekly"), Job("B", 300, "Weekly")],
            expenses=[Expense("E", 100, "Bills", "2024-01-01", "Weekly")],
            balance=0.0,
        )
        # base = 500, 10% raise → 550, net = 450/wk, over 1 wk = 450
        assert abs(state.project_balance(1, {"raise_percent": 0.1}) - 450.0) < 0.001


# ═════════════════════════════════════════════════════════════════════════════
#  6. GOALS
# ═════════════════════════════════════════════════════════════════════════════

class TestGoals:

    def test_weeks_to_goal_simple(self):
        state = FakeState(
            jobs=[Job("Job", 500, "Weekly")],
            expenses=[Expense("E", 400, "Bills", "2024-01-01", "Weekly")],
            balance=0.0,
        )
        # net = 100/wk, goal = 500 → 5 weeks
        assert state.weeks_to_goal(500) == 5

    def test_weeks_to_goal_with_head_start(self):
        state = FakeState(
            jobs=[Job("Job", 500, "Weekly")],
            expenses=[Expense("E", 400, "Bills", "2024-01-01", "Weekly")],
            balance=400.0,
        )
        # need 100 more → 1 week
        assert state.weeks_to_goal(500) == 1

    def test_weeks_to_goal_negative_flow_returns_none(self):
        state = FakeState(
            expenses=[Expense("E", 100, "Bills", "2024-01-01", "Weekly")],
            balance=200.0,
        )
        assert state.weeks_to_goal(500) is None

    def test_weeks_to_goal_zero_flow_returns_none(self):
        assert FakeState(balance=100.0).weeks_to_goal(500) is None

    def test_goal_progress_25_percent(self, base_state):
        # balance = 1000, goal = 4000 → 25%
        assert abs(base_state.goal_progress(4000) - 25.0) < 0.001

    def test_goal_progress_over_100(self, base_state):
        # balance = 1000 > goal = 500
        assert base_state.goal_progress(500) > 100.0

    def test_goal_progress_zero_goal_returns_none(self, base_state):
        assert base_state.goal_progress(0) is None


# ═════════════════════════════════════════════════════════════════════════════
#  7. SCORES
# ═════════════════════════════════════════════════════════════════════════════

class TestScores:

    def test_health_excellent_above_30_percent(self):
        state = FakeState(
            jobs=[Job("Job", 1000, "Weekly")],
            expenses=[Expense("E", 600, "Bills", "2024-01-01", "Weekly")],
        )
        # savings = 40% → 90
        assert state.financial_health_score() == 90

    def test_health_good_at_20_percent(self, base_state):
        # savings = 20% → 75
        assert base_state.financial_health_score() == 75

    def test_health_ok_at_10_percent(self):
        state = FakeState(
            jobs=[Job("Job", 100, "Weekly")],
            expenses=[Expense("E", 90, "Bills", "2024-01-01", "Weekly")],
        )
        assert state.financial_health_score() == 60

    def test_health_break_even(self):
        state = FakeState(
            jobs=[Job("Job", 200, "Weekly")],
            expenses=[Expense("E", 200, "Bills", "2024-01-01", "Weekly")],
        )
        assert state.financial_health_score() == 50

    def test_health_deficit(self):
        state = FakeState(
            jobs=[Job("Job", 100, "Weekly")],
            expenses=[Expense("E", 200, "Bills", "2024-01-01", "Weekly")],
        )
        assert state.financial_health_score() == 20

    def test_risk_score_stable(self, base_state):
        # net > 0, savings = 20% (+20), expenses/income = 0.8 (not strictly >0.8), balance > 0
        # 50 + 20 = 70
        assert base_state.risk_score() == 70

    def test_risk_lower_with_zero_balance(self):
        state = FakeState(
            jobs=[Job("Job", 500, "Weekly")],
            expenses=[Expense("E", 400, "Bills", "2024-01-01", "Weekly")],
            balance=0.0,
        )
        # 50 + 20 - 10 = 60
        assert state.risk_score() == 60

    def test_risk_score_deficit_hits_zero(self):
        state = FakeState(
            jobs=[Job("Job", 100, "Weekly")],
            expenses=[Expense("E", 200, "Bills", "2024-01-01", "Weekly")],
            balance=0.0,
        )
        # many deductions → capped at 0
        assert state.risk_score() == 0

    def test_risk_score_never_above_100(self):
        state = FakeState(
            jobs=[Job("Job", 100_000, "Weekly")],
            expenses=[Expense("E", 1, "Bills", "2024-01-01", "Weekly")],
            balance=1_000_000.0,
        )
        assert state.risk_score() <= 100

    def test_risk_score_never_below_0(self):
        state = FakeState(balance=-999.0)
        assert state.risk_score() >= 0


# ═════════════════════════════════════════════════════════════════════════════
#  8. INSIGHT ENGINE
# ═════════════════════════════════════════════════════════════════════════════

class TestInsightEngine:

    @pytest.fixture(autouse=True)
    def setup(self, base_state):
        self.engine = InsightEngine()
        self.state  = base_state

    # Labels
    def test_risk_label_very_stable(self):  assert self.engine.risk_label(85) == "Very Stable"
    def test_risk_label_stable(self):        assert self.engine.risk_label(65) == "Stable"
    def test_risk_label_moderate(self):      assert self.engine.risk_label(50) == "Moderate Risk"
    def test_risk_label_high_risk(self):     assert self.engine.risk_label(20) == "High Risk"
    def test_health_label_excellent(self):   assert self.engine.health_label(90) == "Excellent"
    def test_health_label_moderate(self):    assert self.engine.health_label(70) == "Moderate"
    def test_health_label_weak(self):        assert self.engine.health_label(50) == "Weak"
    def test_health_label_critical(self):    assert self.engine.health_label(20) == "Critical"

    # Delegation (single source of truth)
    def test_risk_score_delegates_to_state(self):
        assert self.engine.risk_score(self.state) == self.state.risk_score()

    def test_health_score_delegates_to_state(self):
        assert self.engine.financial_health_score(self.state) == self.state.financial_health_score()

    # Insights
    def test_insights_returns_non_empty_list(self):
        insights = self.engine.generate_insights(self.state)
        assert isinstance(insights, list)
        assert len(insights) > 0

    def test_insights_surplus_mentioned(self):
        insights = self.engine.generate_insights(self.state)
        assert any("surplus" in i.lower() for i in insights)

    def test_insights_deficit_mentioned(self):
        state = FakeState(
            jobs=[Job("Job", 100, "Weekly")],
            expenses=[Expense("E", 200, "Bills", "2024-01-01", "Weekly")],
        )
        insights = self.engine.generate_insights(state)
        assert any("deficit" in i.lower() for i in insights)

    def test_insights_top_category_mentioned(self):
        insights = self.engine.generate_insights(self.state)
        assert any("Housing" in i for i in insights)

    def test_insights_all_strings(self):
        for insight in self.engine.generate_insights(self.state):
            assert isinstance(insight, str)


# ═════════════════════════════════════════════════════════════════════════════
#  9. SCENARIO ENGINE
# ═════════════════════════════════════════════════════════════════════════════

class TestScenarioEngine:

    @pytest.fixture(autouse=True)
    def setup(self, base_state):
        self.engine = ScenarioEngine()
        self.state  = base_state  # income 500, expenses 400, net 100, balance 1000

    def test_project_balance_baseline(self):
        s = Scenario("Baseline")
        # net = 100/wk → 1000 + 400 = 1400
        assert abs(self.engine.project_balance(self.state, 4, s) - 1400.0) < 0.01

    def test_project_balance_with_raise(self):
        s = Scenario("Raise", raise_percent=0.1)
        # income → 550, net → 150/wk → 1000 + 600 = 1600
        assert abs(self.engine.project_balance(self.state, 4, s) - 1600.0) < 0.01

    def test_project_balance_with_extra_income(self):
        s = Scenario("Side hustle", extra_weekly=100)
        # income → 600, net → 200/wk → 1000 + 800 = 1800
        assert abs(self.engine.project_balance(self.state, 4, s) - 1800.0) < 0.01

    def test_compare_scenarios_sorted_descending(self):
        scenarios = [
            Scenario("Low",  extra_weekly=50),    # net 150 → bal 1600
            Scenario("High", extra_weekly=200),   # net 300 → bal 2200
        ]
        results = self.engine.compare_scenarios(self.state, 4, scenarios)
        assert results[0]["projected_balance"] >= results[1]["projected_balance"]

    def test_compare_scenarios_required_keys(self):
        results = self.engine.compare_scenarios(self.state, 4, [Scenario("A")])
        for key in ("name", "projected_balance", "net_weekly_flow"):
            assert key in results[0]

    def test_compare_scenarios_correct_names(self):
        scenarios = [Scenario("Alpha"), Scenario("Beta")]
        results   = self.engine.compare_scenarios(self.state, 4, scenarios)
        names     = {r["name"] for r in results}
        assert {"Alpha", "Beta"} == names

    def test_compare_scenarios_count(self):
        scenarios = [Scenario("A"), Scenario("B"), Scenario("C")]
        results   = self.engine.compare_scenarios(self.state, 4, scenarios)
        assert len(results) == 3


# ═════════════════════════════════════════════════════════════════════════════
#  10. SIMULATION — WHAT-IF
# ═════════════════════════════════════════════════════════════════════════════

class TestWhatIfSimulation:

    @pytest.fixture(autouse=True)
    def setup(self, base_state):
        self.state = base_state   # balance 1000, net 100/wk

    def test_history_correct_length(self):
        result = simulate_whatif(self.state, "Test", -100, 5)
        assert len(result["history"]) == 5

    def test_week1_negative_event(self):
        result = simulate_whatif(self.state, "Car repair", -200, 3)
        # week1: 1000 - 200 + 100 = 900
        assert abs(result["history"][0]["balance"] - 900.0) < 0.01

    def test_week1_positive_event(self):
        result = simulate_whatif(self.state, "Bonus", 300, 3)
        # week1: 1000 + 300 + 100 = 1400
        assert abs(result["history"][0]["balance"] - 1400.0) < 0.01

    def test_subsequent_weeks_apply_net_flow(self):
        result = simulate_whatif(self.state, "Test", 0, 3)
        # every week: +100/wk
        assert abs(result["history"][0]["balance"] - 1100.0) < 0.01
        assert abs(result["history"][1]["balance"] - 1200.0) < 0.01
        assert abs(result["history"][2]["balance"] - 1300.0) < 0.01

    def test_has_summary_string(self):
        result = simulate_whatif(self.state, "Test", -100, 2)
        assert isinstance(result.get("summary"), str)
        assert len(result["summary"]) > 0

    def test_has_history_key(self):
        assert "history" in simulate_whatif(self.state, "Test", 0, 1)

    def test_week1_note_contains_description(self):
        result = simulate_whatif(self.state, "Got sick", -50, 2)
        assert "Got sick" in result["history"][0]["note"]

    def test_week2_note_is_regular(self):
        result = simulate_whatif(self.state, "Test", -50, 3)
        assert "Regular week" in result["history"][1]["note"]

    def test_zero_dollar_impact(self):
        result = simulate_whatif(self.state, "Nothing happened", 0, 2)
        assert len(result["history"]) == 2


# ═════════════════════════════════════════════════════════════════════════════
#  11. SIMULATION — MONTE CARLO
# ═════════════════════════════════════════════════════════════════════════════

class TestMonteCarlo:

    @pytest.fixture(autouse=True)
    def setup(self, base_state):
        self.state = base_state

    def test_required_keys_present(self):
        r = run_monte_carlo(self.state, weeks=4, n=50)
        for key in ["average", "best_case", "worst_case",
                    "deficit_probability", "safe_probability",
                    "plain_summary", "ending_balances", "n", "weeks"]:
            assert key in r

    def test_probabilities_sum_to_100(self):
        r = run_monte_carlo(self.state, weeks=4, n=100)
        assert abs(r["deficit_probability"] + r["safe_probability"] - 100.0) < 0.01

    def test_ending_balances_length_equals_n(self):
        r = run_monte_carlo(self.state, weeks=4, n=80)
        assert len(r["ending_balances"]) == 80

    def test_best_case_at_least_average(self):
        r = run_monte_carlo(self.state, weeks=4, n=100)
        assert r["best_case"] >= r["average"]

    def test_worst_case_at_most_average(self):
        r = run_monte_carlo(self.state, weeks=4, n=100)
        assert r["worst_case"] <= r["average"]

    def test_n_and_weeks_echoed_in_result(self):
        r = run_monte_carlo(self.state, weeks=12, n=50)
        assert r["n"] == 50
        assert r["weeks"] == 12

    def test_plain_summary_is_non_empty_string(self):
        r = run_monte_carlo(self.state, weeks=4, n=50)
        assert isinstance(r["plain_summary"], str)
        assert len(r["plain_summary"]) > 10

    def test_deficit_probability_between_0_and_100(self):
        r = run_monte_carlo(self.state, weeks=4, n=100)
        assert 0 <= r["deficit_probability"] <= 100


# ═════════════════════════════════════════════════════════════════════════════
#  12. DATABASE
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def temp_db(monkeypatch, tmp_path):
    """Point db_connection.SQLITE_FILE at a fresh temp file for each test."""
    db_file = str(tmp_path / "test_shiftiq.db")
    monkeypatch.setattr(db_connection, "SQLITE_FILE", db_file)
    database.init_db()
    return db_file


class TestDatabase:

    def test_init_creates_all_tables(self, temp_db):
        import sqlite3
        with sqlite3.connect(temp_db) as conn:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
        assert {"jobs", "expenses", "settings", "history"}.issubset(tables)

    def test_insert_and_load_job(self, temp_db):
        database.insert_job(Job("Barista", 300, "Weekly"))
        jobs = database.load_jobs()
        assert len(jobs) == 1
        assert jobs[0].name      == "Barista"
        assert jobs[0].amount    == 300
        assert jobs[0].frequency == "Weekly"

    def test_insert_duplicate_job_ignored(self, temp_db):
        job = Job("Barista", 300, "Weekly")
        database.insert_job(job)
        database.insert_job(job)
        assert len(database.load_jobs()) == 1

    def test_remove_job(self, temp_db):
        database.insert_job(Job("Barista", 300, "Weekly"))
        database.remove_job("Barista")
        assert len(database.load_jobs()) == 0

    def test_remove_nonexistent_job_does_not_crash(self, temp_db):
        database.remove_job("Nobody")   # should not raise

    def test_insert_and_load_expense(self, temp_db):
        database.insert_expense(Expense("Rent", 1200, "Housing", "2024-01-01", "Monthly"))
        expenses = database.load_expenses()
        assert len(expenses) == 1
        assert expenses[0].name      == "Rent"
        assert expenses[0].amount    == 1200
        assert expenses[0].frequency == "Monthly"

    def test_remove_expense(self, temp_db):
        database.insert_expense(Expense("Rent", 1200, "Housing", "2024-01-01", "Monthly"))
        database.remove_expense("Rent")
        assert len(database.load_expenses()) == 0

    def test_balance_default_is_zero(self, temp_db):
        assert database.load_balance() == 0.0

    def test_save_and_load_balance(self, temp_db):
        database.save_balance(750.50)
        assert abs(database.load_balance() - 750.50) < 0.001

    def test_save_balance_updates_existing(self, temp_db):
        database.save_balance(100)
        database.save_balance(200)
        assert abs(database.load_balance() - 200.0) < 0.001

    def test_record_and_load_snapshot(self, temp_db):
        database.record_snapshot(1000.0, 500.0, 400.0, 100.0)
        history = database.load_history()
        assert len(history) == 1
        assert abs(history[0]["balance"]  - 1000.0) < 0.001
        assert abs(history[0]["income"]   -  500.0) < 0.001
        assert abs(history[0]["expenses"] -  400.0) < 0.001
        assert abs(history[0]["net"]      -  100.0) < 0.001

    def test_snapshot_one_record_per_day(self, temp_db):
        # Two calls on the same day → only one row, last value wins
        database.record_snapshot(1000.0, 500.0, 400.0, 100.0)
        database.record_snapshot(1500.0, 600.0, 400.0, 200.0)
        history = database.load_history()
        assert len(history) == 1
        assert abs(history[0]["balance"] - 1500.0) < 0.001

    def test_history_returned_in_date_order(self, temp_db):
        import sqlite3
        with sqlite3.connect(temp_db) as conn:
            for date in ("2024-01-03", "2024-01-01", "2024-01-02"):
                conn.execute(
                    "INSERT INTO history (date, balance, income_weekly, expenses_weekly, net_weekly)"
                    " VALUES (?, ?, ?, ?, ?)", (date, 0, 0, 0, 0)
                )
            conn.commit()
        dates = [h["date"] for h in database.load_history()]
        assert dates == sorted(dates)

    def test_backup_creates_file(self, temp_db, tmp_path):
        database.save_balance(500)
        dest = database.backup_database()
        assert os.path.exists(dest)
        assert dest.endswith(".db")
        assert "backup_" in os.path.basename(dest)


# ═════════════════════════════════════════════════════════════════════════════
#  13. UTILS — canon_name  (single source of truth regression)
# ═════════════════════════════════════════════════════════════════════════════

from backend.core.utils import canon_name, normalize_job_name

class TestCanonName:

    def test_strips_trailing_s_long_name(self):
        assert canon_name("admissions") == "Admission"

    def test_preserves_short_name_under_5_chars(self):
        # len("jobs") == 4 — the condition is len > 4, so "jobs" (4 chars) gets stripped
        # len("oip") == 3 — no strip
        assert canon_name("oip") == "Oip"

    def test_exactly_5_chars_gets_stripped(self):
        # "names" has len 5 and ends in 's' → strip
        assert canon_name("names") == "Name"

    def test_title_cases_result(self):
        assert canon_name("DINING SERVICES") == "Dining Service"

    def test_idempotent(self):
        name = "Dining Service"
        assert canon_name(canon_name(name)) == canon_name(name)

    def test_whitespace_stripped(self):
        assert canon_name("  Admissions  ") == "Admission"

    def test_consistent_across_case_variants(self):
        variants = ["admissions", "Admissions", "ADMISSIONS", "AdMiSsIoNs"]
        results  = [canon_name(v) for v in variants]
        assert len(set(results)) == 1, f"Expected all equal, got {results}"

    def test_no_trailing_s_untouched(self):
        assert canon_name("Rent") == "Rent"

    def test_normalize_exact_match(self):
        existing = ["Admission", "Dining Service"]
        assert normalize_job_name("Admissions", existing) == "Admission"

    def test_normalize_new_name_returns_canon(self):
        assert normalize_job_name("brand new jobs", []) == "Brand New Job"

    def test_normalize_empty_returns_empty(self):
        assert normalize_job_name("", ["anything"]) == ""


# ═════════════════════════════════════════════════════════════════════════════
#  14. SCENARIO ENGINE — extra_weekly bug regression
# ═════════════════════════════════════════════════════════════════════════════

class TestScenarioEngineBugRegression:
    """
    extra_weekly must be added ONCE to total income, not once per job.
    Before the fix: user with 3 jobs × extra_weekly=50 → +$150 (wrong).
    After the fix:  regardless of job count → always +$50 (correct).
    """

    def _state_n_jobs(self, n):
        return FakeState(
            jobs=[Job(f"Job {i}", 100, "Weekly") for i in range(n)],
            expenses=[],
            balance=0.0,
        )

    def test_extra_weekly_same_for_1_job(self):
        engine   = ScenarioEngine()
        scenario = Scenario("Test", extra_weekly=50.0)
        result   = engine.project_balance(self._state_n_jobs(1), weeks=1, scenario=scenario)
        # 1 job × $100 + $50 extra = $150 net (no expenses)
        assert abs(result - 150.0) < 0.01

    def test_extra_weekly_same_for_3_jobs(self):
        engine   = ScenarioEngine()
        scenario = Scenario("Test", extra_weekly=50.0)
        result   = engine.project_balance(self._state_n_jobs(3), weeks=1, scenario=scenario)
        # 3 jobs × $100 = $300 base + $50 extra (once) = $350 net
        assert abs(result - 350.0) < 0.01, (
            f"Got {result} — extra_weekly is probably being multiplied by job count"
        )

    def test_extra_weekly_does_not_scale_with_job_count(self):
        engine   = ScenarioEngine()
        scenario = Scenario("Test", extra_weekly=50.0)
        b1 = engine.project_balance(self._state_n_jobs(1), weeks=1, scenario=scenario)
        b3 = engine.project_balance(self._state_n_jobs(3), weeks=1, scenario=scenario)
        # Difference must be exactly 2 × $100 (two extra jobs), not 2 × ($100+$50)
        assert abs((b3 - b1) - 200.0) < 0.01, (
            f"b3={b3}, b1={b1}, diff={b3-b1} — expected 200, not 300"
        )


# ═════════════════════════════════════════════════════════════════════════════
#  15. SCHEDULE ANALYTICS — pure functions
# ═════════════════════════════════════════════════════════════════════════════

import backend.core.shift_analytics as sa
import datetime

def _make_event(title="Job A", category="Work", day="Monday",
                start="09:00", end="17:00", rate=15.0,
                shift_date="2026-06-16", notes=""):
    """Helper — creates a minimal ScheduleEvent-like object."""
    from backend.core.schedule_event import ScheduleEvent
    return ScheduleEvent(
        title=title, category=category, day=day,
        start_time=start, end_time=end,
        hourly_rate=rate, notes=notes, shift_date=shift_date,
    )


class TestScheduleAnalytics:

    def _sample_events(self):
        return [
            _make_event("Job A", "Work",   "Monday",    "09:00", "17:00", 15.0, "2026-06-16"),
            _make_event("Job A", "Work",   "Wednesday", "09:00", "13:00", 15.0, "2026-06-18"),
            _make_event("Job B", "Work",   "Tuesday",   "10:00", "14:00", 20.0, "2026-06-17"),
            _make_event("Class","School",  "Monday",    "08:00", "09:00",  0.0, "2026-06-16"),
        ]

    def test_income_by_job_ignores_non_work(self):
        groups = sa.income_by_job(self._sample_events())
        for key in groups:
            assert "Class" not in key
            assert "School" not in key

    def test_income_by_job_groups_by_canon_name(self):
        # "Job A" appears twice — must be one group
        groups = sa.income_by_job(self._sample_events())
        job_a_keys = [k for k in groups if "Job" in k and "B" not in k]
        assert len(job_a_keys) == 1

    def test_income_by_job_hours_summed_correctly(self):
        groups = sa.income_by_job(self._sample_events())
        job_a  = next(g for g in groups.values() if "A" in g.name or "A" in list(groups.keys())[0])
        # Job A: 8h + 4h = 12h
        assert abs(job_a.total_hours - 12.0) < 0.01

    def test_daily_totals_skips_no_shift_date(self):
        events = [_make_event(shift_date="")]   # no date
        totals = sa.daily_totals(events)
        assert len(totals) == 0

    def test_daily_totals_correct_value(self):
        events = [_make_event("Job A", "Work", "Monday", "09:00", "17:00", 15.0, "2026-06-16")]
        totals = sa.daily_totals(events)
        assert "2026-06-16" in totals
        assert abs(totals["2026-06-16"] - 8 * 15.0) < 0.01

    def test_shift_hours_overnight(self):
        ev = _make_event(start="22:00", end="06:00")
        assert abs(sa._shift_hours(ev) - 8.0) < 0.01

    def test_shift_hours_normal(self):
        ev = _make_event(start="09:00", end="17:00")
        assert abs(sa._shift_hours(ev) - 8.0) < 0.01

    def test_shift_hours_zero_same_start_end(self):
        ev = _make_event(start="09:00", end="09:00")
        assert sa._shift_hours(ev) == 0.0

    def test_date_range_summary_total_hours(self):
        summary = sa.date_range_summary(self._sample_events())
        # Job A: 8+4=12h, Job B: 4h → 16h total
        assert abs(summary.total_hours - 16.0) < 0.01

    def test_date_range_summary_work_days(self):
        summary = sa.date_range_summary(self._sample_events())
        # Mon (Job A), Tue (Job B), Wed (Job A) → 3 work days
        assert summary.work_days == 3

    def test_top_earning_days_sorted(self):
        events = [
            _make_event(rate=15.0, shift_date="2026-06-16", start="09:00", end="17:00"),  # $120
            _make_event(rate=20.0, shift_date="2026-06-17", start="10:00", end="14:00"),  # $80
        ]
        top = sa.top_earning_days(events, n=2)
        assert top[0][1] >= top[1][1]

    def test_variant_spellings_one_group(self):
        events = [
            _make_event("admissions", rate=14.0, shift_date="2026-06-16"),
            _make_event("Admissions", rate=14.0, shift_date="2026-06-17"),
            _make_event("ADMISSIONS", rate=14.0, shift_date="2026-06-18"),
        ]
        groups = sa.income_by_job(events)
        assert len(groups) == 1, f"Expected 1 group, got {len(groups)}: {list(groups.keys())}"


# ═════════════════════════════════════════════════════════════════════════════
#  16. DECISION ENGINE — ShiftImpact
# ═════════════════════════════════════════════════════════════════════════════

class TestShiftImpact:

    def _state(self, weekly_income=800.0, weekly_expenses=600.0):
        return FakeState(
            jobs=[Job("Job", weekly_income, "Weekly")],
            expenses=[Expense("E", weekly_expenses, "Bills", "", "Weekly")],
            balance=500.0,
        )

    def test_basic_8h_shift_income_lost(self):
        ev     = _make_event(start="09:00", end="17:00", rate=15.0)
        impact = sa.shift_impact(ev, self._state())
        assert abs(impact.hours_lost  - 8.0)   < 0.01
        assert abs(impact.income_lost - 120.0) < 0.01

    def test_new_weekly_income_reduced(self):
        ev     = _make_event(start="09:00", end="17:00", rate=15.0)
        impact = sa.shift_impact(ev, self._state(weekly_income=800.0))
        assert abs(impact.new_weekly_income - (800.0 - 120.0)) < 0.01

    def test_deficit_triggers_warning_in_recommendation(self):
        # shift earns $400, income is $500 → removing puts net into deficit
        ev     = _make_event(start="09:00", end="17:00", rate=50.0)  # 8h × $50 = $400
        impact = sa.shift_impact(ev, self._state(weekly_income=500.0, weekly_expenses=450.0))
        assert impact.new_net_flow < 0
        assert "deficit" in impact.recommendation.lower()

    def test_manageable_shift_positive_recommendation(self):
        # remove small shift from large income
        ev     = _make_event(start="09:00", end="11:00", rate=10.0)  # 2h × $10 = $20
        impact = sa.shift_impact(ev, self._state(weekly_income=1000.0, weekly_expenses=400.0))
        assert impact.new_net_flow > 0
        assert "manageable" in impact.recommendation.lower()

    def test_overnight_shift_hours_correct(self):
        ev     = _make_event(start="22:00", end="06:00", rate=20.0)  # 8h
        impact = sa.shift_impact(ev, self._state())
        assert abs(impact.hours_lost  - 8.0)   < 0.01
        assert abs(impact.income_lost - 160.0) < 0.01

    def test_zero_rate_shift_no_income_lost(self):
        ev     = _make_event(start="09:00", end="17:00", rate=0.0)
        impact = sa.shift_impact(ev, self._state())
        assert impact.income_lost        == 0.0
        assert impact.new_weekly_income  == pytest.approx(800.0)

    def test_pct_change_is_negative(self):
        ev     = _make_event(start="09:00", end="17:00", rate=15.0)
        impact = sa.shift_impact(ev, self._state())
        assert impact.weekly_income_pct_change < 0


# ═════════════════════════════════════════════════════════════════════════════
#  17. DECISION ENGINE — JobEfficiency
# ═════════════════════════════════════════════════════════════════════════════

class TestJobEfficiency:

    def _two_job_events(self):
        return [
            _make_event("Job A", rate=20.0, start="09:00", end="17:00", shift_date="2026-06-16"),
            _make_event("Job A", rate=20.0, start="09:00", end="17:00", shift_date="2026-06-17"),
            _make_event("Job B", rate=12.0, start="07:00", end="13:00", shift_date="2026-06-18"),
        ]

    def test_returns_list(self):
        assert isinstance(sa.job_efficiency_report(self._two_job_events()), list)

    def test_sorted_by_income_per_hour_desc(self):
        report = sa.job_efficiency_report(self._two_job_events())
        assert report[0].income_per_hour >= report[-1].income_per_hour

    def test_early_start_flagged(self):
        # Job B starts at 07:00 which is < 08:00
        report = sa.job_efficiency_report(self._two_job_events())
        job_b  = next(j for j in report if "B" in j.name)
        assert job_b.early_starts == 1

    def test_no_friction_job_gets_favorable_note(self):
        events = [_make_event("Good Job", rate=25.0, start="10:00", end="16:00")]
        report = sa.job_efficiency_report(events)
        assert "favorable" in report[0].efficiency_note.lower()

    def test_empty_events_returns_empty_list(self):
        assert sa.job_efficiency_report([]) == []


# ═════════════════════════════════════════════════════════════════════════════
#  18. STRESS TESTS
# ═════════════════════════════════════════════════════════════════════════════

import time
import random

class TestStress:

    def _large_event_set(self, n=2000):
        """Generate n random Work events with variant names and mixed rates."""
        events = []
        base   = datetime.date(2025, 1, 1)
        job_variants = [
            ("Job A", "Job A"), ("job a", "Job A"), ("JOB A", "Job A"),
            ("Job B", "Job B"), ("job b", "Job B"),
        ]
        for i in range(n):
            d        = base + datetime.timedelta(days=random.randint(0, 364))
            raw, _   = random.choice(job_variants)
            start_h  = random.randint(6, 14)
            end_h    = start_h + random.randint(2, 8)
            if end_h > 23: end_h = 23
            rate     = random.choice([0.0, 14.0, 15.0, 20.0])
            events.append(_make_event(
                title=raw, category="Work", day=d.strftime("%A"),
                start=f"{start_h:02d}:00", end=f"{end_h:02d}:00",
                rate=rate, shift_date=d.isoformat(),
            ))
        return events

    def test_large_event_performance(self):
        events  = self._large_event_set(2000)
        start   = time.perf_counter()
        summary = sa.date_range_summary(events)
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"date_range_summary took {elapsed:.3f}s on 2000 events (limit: 1s)"
        assert summary.total_hours > 0

    def test_variant_spellings_exactly_two_groups(self):
        events = self._large_event_set(500)
        groups = sa.income_by_job(events)
        # Despite variant spellings, should resolve to exactly 2 canonical groups
        assert len(groups) == 2, (
            f"Expected 2 groups (Job A, Job B), got {len(groups)}: {list(groups.keys())}"
        )

    def test_zero_income_state_no_crash(self):
        state = FakeState()  # no jobs, no expenses, balance 0
        assert state.savings_rate()              == 0.0
        assert state.risk_score()                >= 0
        assert state.total_income_per_week()     == 0.0
        assert state.net_weekly_flow()           == 0.0

    def test_shift_impact_zero_income_state_no_crash(self):
        ev     = _make_event(rate=15.0)
        state  = FakeState()
        impact = sa.shift_impact(ev, state)
        assert isinstance(impact.recommendation, str)

    def test_all_zero_rate_events_no_income(self):
        events = [_make_event(rate=0.0, shift_date=f"2026-06-{d:02d}") for d in range(1, 8)]
        groups = sa.income_by_job(events)
        for group in groups.values():
            assert group.total_income == 0.0

    def test_legacy_events_no_shift_date_dont_crash_daily_totals(self):
        events = [_make_event(shift_date="") for _ in range(20)]
        totals = sa.daily_totals(events)
        assert totals == {}   # all excluded — no crash


# ═════════════════════════════════════════════════════════════════════════════
#  19. SHIFT OPTIMIZER (knapsack-style constrained selection)
# ═════════════════════════════════════════════════════════════════════════════

import backend.core.optimizer as opt


class TestShiftOptimizer:

    def test_empty_candidates_returns_empty_result(self):
        result = opt.optimize_shift_selection([], max_hours=20)
        assert result.selected == []
        assert result.total_income == 0.0

    def test_zero_or_negative_budget_returns_empty_result(self):
        cands = [opt.ShiftCandidate("a", "A", hours=5, hourly_rate=10)]
        assert opt.optimize_shift_selection(cands, max_hours=0).selected == []
        assert opt.optimize_shift_selection(cands, max_hours=-5).selected == []

    def test_single_candidate_within_budget_is_selected(self):
        cands  = [opt.ShiftCandidate("a", "A", hours=5, hourly_rate=10)]
        result = opt.optimize_shift_selection(cands, max_hours=10)
        assert [c.id for c in result.selected] == ["a"]
        assert result.total_income == 50.0

    def test_single_candidate_exceeding_budget_is_excluded(self):
        cands  = [opt.ShiftCandidate("a", "A", hours=15, hourly_rate=10)]
        result = opt.optimize_shift_selection(cands, max_hours=10)
        assert result.selected == []
        assert result.total_income == 0.0

    def test_beats_naive_greedy_by_rate(self):
        """
        Knapsack DP must find the true optimum even when the
        highest-$/hr single shift is NOT part of the best combination —
        the scenario where greedy-by-rate selection fails.
        """
        candidates = [
            opt.ShiftCandidate("x", "Job X", hours=9, hourly_rate=20),  # $180, highest rate
            opt.ShiftCandidate("y", "Job Y", hours=5, hourly_rate=19),  # $95
            opt.ShiftCandidate("z", "Job Z", hours=5, hourly_rate=19),  # $95
        ]
        result = opt.optimize_shift_selection(candidates, max_hours=10)
        greedy_best_single = max(c.income for c in candidates if c.hours <= 10)

        assert sorted(c.id for c in result.selected) == ["y", "z"]
        assert result.total_income == 190.0
        assert result.total_income > greedy_best_single

    def test_all_candidates_fit_selects_everything(self):
        cands = [
            opt.ShiftCandidate("a", "A", hours=4, hourly_rate=12),
            opt.ShiftCandidate("b", "B", hours=4, hourly_rate=15),
        ]
        result = opt.optimize_shift_selection(cands, max_hours=20)
        assert len(result.selected) == 2
        assert result.total_hours == 8.0
        assert result.hours_unused == 12.0

    def test_effective_rate_is_blended_average(self):
        cands  = [
            opt.ShiftCandidate("a", "A", hours=2, hourly_rate=10),  # $20
            opt.ShiftCandidate("b", "B", hours=2, hourly_rate=20),  # $40
        ]
        result = opt.optimize_shift_selection(cands, max_hours=10)
        assert result.total_income == 60.0
        assert result.effective_rate == 15.0   # ($20+$40) / 4h

    def test_candidates_from_events_skips_non_work_and_zero_rate(self):
        events = [
            _make_event(title="Study", category="Study", rate=0.0),
            _make_event(title="Job A", category="Work",  rate=0.0),
            _make_event(title="Job B", category="Work",  rate=15.0,
                        start="09:00", end="13:00"),
        ]
        cands = opt.candidates_from_events(events)
        assert len(cands) == 1
        assert cands[0].job_name == "Job B"
        assert cands[0].hours == 4.0

    def test_candidates_from_events_handles_overnight_shift(self):
        events = [_make_event(title="Night Shift", category="Work",
                               rate=15.0, start="22:00", end="06:00")]
        cands = opt.candidates_from_events(events)
        assert cands[0].hours == 8.0

    def test_end_to_end_with_real_schedule_events(self):
        """Optimizer should work directly on ScheduleEvent objects via the adapter."""
        events = [
            _make_event(title="Job A", category="Work", rate=20.0,
                         start="08:00", end="17:00"),   # 9h, $180
            _make_event(title="Job B", category="Work", rate=19.0,
                         start="08:00", end="13:00"),   # 5h, $95
            _make_event(title="Job C", category="Work", rate=19.0,
                         start="13:00", end="18:00"),   # 5h, $95
        ]
        cands  = opt.candidates_from_events(events)
        result = opt.optimize_shift_selection(cands, max_hours=10)
        assert result.total_income == 190.0
        assert {c.job_name for c in result.selected} == {"Job B", "Job C"}


# ═════════════════════════════════════════════════════════════════════════════
#  DAY 15 — FinancialState: add/delete/validate (real class, temp DB)
# ═════════════════════════════════════════════════════════════════════════════

import backend.core.financial_state as fs_module


@pytest.fixture
def fs(monkeypatch, tmp_path):
    """Real FinancialState wired to an empty temp database."""
    db_file = str(tmp_path / "fs_test.db")
    monkeypatch.setattr(db_connection, "SQLITE_FILE", db_file)
    monkeypatch.setattr(fs_module, "activity_log", type("_", (), {"log": staticmethod(lambda *a: None)})())
    return fs_module.FinancialState()


class TestFinancialStateAddDelete:

    def test_add_job_success(self, fs):
        ok, msg = fs.add_job(Job("Barista", 300, "Weekly"))
        assert ok
        assert "Barista" in msg

    def test_add_job_persists_to_db(self, fs):
        fs.add_job(Job("Barista", 300, "Weekly"))
        assert len(database.load_jobs()) == 1

    def test_add_job_duplicate_rejected(self, fs):
        fs.add_job(Job("Barista", 300, "Weekly"))
        ok, msg = fs.add_job(Job("Barista", 400, "Weekly"))
        assert not ok
        assert "already exists" in msg.lower()

    def test_add_job_blank_name_rejected(self, fs):
        ok, msg = fs.add_job(Job("", 300, "Weekly"))
        assert not ok

    def test_add_job_zero_amount_rejected(self, fs):
        ok, msg = fs.add_job(Job("X", 0, "Weekly"))
        assert not ok

    def test_add_job_negative_amount_rejected(self, fs):
        ok, msg = fs.add_job(Job("X", -50, "Weekly"))
        assert not ok

    def test_delete_job_success(self, fs):
        fs.add_job(Job("Barista", 300, "Weekly"))
        ok, msg = fs.delete_job("Barista")
        assert ok
        assert len(fs.jobs) == 0

    def test_delete_job_removes_from_db(self, fs):
        fs.add_job(Job("Barista", 300, "Weekly"))
        fs.delete_job("Barista")
        assert len(database.load_jobs()) == 0

    def test_delete_nonexistent_job_returns_false(self, fs):
        ok, msg = fs.delete_job("Ghost")
        assert not ok
        assert "not found" in msg.lower()

    def test_add_expense_success(self, fs):
        ok, _ = fs.add_expense(Expense("Rent", 800, "Housing", "2026-01-01", "Monthly"))
        assert ok

    def test_add_expense_blank_name_rejected(self, fs):
        ok, _ = fs.add_expense(Expense("", 100, "Food", "2026-01-01", "Monthly"))
        assert not ok

    def test_add_expense_blank_category_rejected(self, fs):
        ok, _ = fs.add_expense(Expense("X", 100, "", "2026-01-01", "Monthly"))
        assert not ok

    def test_add_expense_zero_amount_rejected(self, fs):
        ok, _ = fs.add_expense(Expense("X", 0, "Food", "2026-01-01", "Monthly"))
        assert not ok

    def test_add_expense_duplicate_rejected(self, fs):
        e = Expense("Rent", 800, "Housing", "2026-01-01", "Monthly")
        fs.add_expense(e)
        ok, msg = fs.add_expense(e)
        assert not ok
        assert "already exists" in msg.lower()

    def test_delete_expense_success(self, fs):
        fs.add_expense(Expense("Rent", 800, "Housing", "2026-01-01", "Monthly"))
        ok, _ = fs.delete_expense("Rent")
        assert ok
        assert len(fs.expenses) == 0

    def test_delete_nonexistent_expense_returns_false(self, fs):
        ok, msg = fs.delete_expense("Ghost")
        assert not ok

    def test_set_balance_success(self, fs):
        ok, msg = fs.set_balance(999.99)
        assert ok
        assert abs(fs.balance - 999.99) < 0.001

    def test_set_balance_persists(self, fs):
        fs.set_balance(1234.56)
        assert abs(database.load_balance() - 1234.56) < 0.001

    def test_set_balance_zero_is_valid(self, fs):
        ok, _ = fs.set_balance(0.0)
        assert ok

    def test_set_balance_non_numeric_rejected(self, fs):
        ok, _ = fs.set_balance("not a number")
        assert not ok

    def test_net_flow_reflects_added_job(self, fs):
        fs.add_job(Job("Work", 500, "Weekly"))
        fs.add_expense(Expense("Rent", 300, "Housing", "2026-01-01", "Weekly"))
        assert abs(fs.net_weekly_flow() - 200.0) < 0.001

    def test_financial_health_score_in_range(self, fs):
        fs.add_job(Job("Work", 500, "Weekly"))
        score = fs.financial_health_score()
        assert 0 <= score <= 100

    def test_risk_score_in_range(self, fs):
        fs.add_job(Job("Work", 500, "Weekly"))
        score = fs.risk_score()
        assert 0 <= score <= 100


# ═════════════════════════════════════════════════════════════════════════════
#  DAY 16 — database.py: settings and load_setting/save_setting
# ═════════════════════════════════════════════════════════════════════════════

class TestDatabaseSettings:

    def test_load_setting_returns_default_when_missing(self, temp_db):
        assert database.load_setting("missing_key", 42.0) == 42.0

    def test_save_and_load_setting(self, temp_db):
        database.save_setting("projection_weeks", 26)
        assert database.load_setting("projection_weeks", 52) == 26

    def test_save_setting_overwrites(self, temp_db):
        database.save_setting("monte_carlo_runs", 100)
        database.save_setting("monte_carlo_runs", 500)
        assert database.load_setting("monte_carlo_runs", 0) == 500

    def test_multiple_settings_independent(self, temp_db):
        database.save_setting("a", 1.0)
        database.save_setting("b", 2.0)
        assert database.load_setting("a", 0) == 1.0
        assert database.load_setting("b", 0) == 2.0

    def test_setting_default_is_float(self, temp_db):
        result = database.load_setting("nope", 7.5)
        assert isinstance(result, float)

    def test_save_balance_and_load_setting_dont_interfere(self, temp_db):
        database.save_balance(999.0)
        database.save_setting("projection_weeks", 12)
        assert abs(database.load_balance() - 999.0) < 0.001
        assert database.load_setting("projection_weeks", 0) == 12


# ═════════════════════════════════════════════════════════════════════════════
#  DAY 17 — exceptions.py: ValidationError hierarchy and propagation
# ═════════════════════════════════════════════════════════════════════════════

from backend.core.exceptions import ValidationError


class TestValidationError:

    def test_is_exception(self):
        assert issubclass(ValidationError, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(ValidationError):
            raise ValidationError("bad input")

    def test_message_preserved(self):
        try:
            raise ValidationError("amount must be positive")
        except ValidationError as e:
            assert "amount must be positive" in str(e)

    def test_caught_by_exception_base(self):
        with pytest.raises(Exception):
            raise ValidationError("test")

    def test_not_caught_by_value_error(self):
        with pytest.raises(ValidationError):
            try:
                raise ValidationError("test")
            except ValueError:
                pass   # must NOT be caught here

    def test_financial_state_raises_validation_error_on_bad_job(self, fs):
        # FinancialState itself returns (False, msg) — ValidationError is for UI layer
        ok, msg = fs.add_job(Job("", 0, "Weekly"))
        assert not ok


# ═════════════════════════════════════════════════════════════════════════════
#  DAY 18 — shift_parser and date_parser
# ═════════════════════════════════════════════════════════════════════════════

import backend.core.shift_parser as shift_parser
import backend.core.date_parser as date_parser


class TestShiftParser:
    """Tests for shift_parser's internal time-normalisation helpers and public API."""

    def test_parse_time_token_24h(self):
        # "14:30" should come back as "14:30"
        assert shift_parser._parse_time_token("14:30") == "14:30"

    def test_parse_time_token_midnight(self):
        assert shift_parser._parse_time_token("00:00") == "00:00"

    def test_parse_time_token_23_59(self):
        assert shift_parser._parse_time_token("23:59") == "23:59"

    def test_parse_time_token_invalid_raises(self):
        with pytest.raises((ValidationError, ValueError, Exception)):
            shift_parser._parse_time_token("25:00")

    def test_parse_time_token_bad_minutes_raises(self):
        with pytest.raises((ValidationError, ValueError, Exception)):
            shift_parser._parse_time_token("10:99")

    def test_normalize_hour_pm_rule(self):
        # Hours 1-7 → PM (add 12)
        assert shift_parser._normalize_hour("5") == 17

    def test_normalize_hour_am_rule(self):
        # Hours 8-12 → AM
        assert shift_parser._normalize_hour("9") == 9

    def test_normalize_hour_24h_passthrough(self):
        assert shift_parser._normalize_hour("22") == 22

    def test_parse_schedule_text_empty_returns_error(self):
        result = shift_parser.parse_schedule_text("")
        assert len(result.errors) > 0

    def test_parse_schedule_text_valid_input(self):
        text = "Job A: Mon 9-5 Wed 10-14"
        result = shift_parser.parse_schedule_text(text)
        # Should parse without fatal errors
        assert isinstance(result.shifts, list)


class TestDateParser:
    """Tests for date_parser.parse_schedule public API.

    Daily mode requires the header "date: YYYY-MM-DD" (case-insensitive).
    Weekly mode requires "week: YYYY-MM-DD". Anything else falls through to
    weekly mode with zero shifts when no valid day blocks are found.
    """

    def test_parse_schedule_daily_mode(self):
        # The daily-mode header is "date: YYYY-MM-DD", not "YYYY-MM-DD:"
        text = "date: 2026-06-15\nJob A 09:00-17:00 @15"
        result = date_parser.parse_schedule(text)
        assert result.mode == "daily"

    def test_parse_schedule_returns_result_object(self):
        text = "date: 2026-06-15\nJob A 09:00-17:00 @15"
        result = date_parser.parse_schedule(text)
        assert hasattr(result, "shifts")
        assert hasattr(result, "errors")

    def test_parse_schedule_empty_input_gives_no_shifts(self):
        result = date_parser.parse_schedule("")
        assert len(result.shifts) == 0

    def test_parse_schedule_unrecognised_header_gives_no_shifts(self):
        # No recognised header → weekly mode, no valid day blocks → 0 shifts
        result = date_parser.parse_schedule("not-a-date: Job A 09:00-17:00")
        assert len(result.shifts) == 0


# ═════════════════════════════════════════════════════════════════════════════
#  DAY 19 — simulation edge cases
# ═════════════════════════════════════════════════════════════════════════════

class TestSimulationEdgeCases:

    def test_whatif_zero_weeks_returns_empty_history(self, base_state):
        result = simulate_whatif(base_state, "Test", 0, 0)
        assert result["history"] == []

    def test_whatif_very_large_positive_shock(self, base_state):
        result = simulate_whatif(base_state, "Lottery", 1_000_000, 1)
        assert result["history"][0]["balance"] > 1_000_000

    def test_whatif_very_large_negative_shock(self, base_state):
        result = simulate_whatif(base_state, "Disaster", -50_000, 1)
        assert result["history"][0]["balance"] < 0   # balance can go negative

    def test_monte_carlo_single_run_stable(self, base_state):
        r = run_monte_carlo(base_state, weeks=4, n=1)
        assert r["n"] == 1
        assert len(r["ending_balances"]) == 1

    def test_monte_carlo_zero_income_high_deficit_probability(self):
        state = FakeState(
            expenses=[Expense("E", 200, "Bills", "2024-01-01", "Weekly")],
            balance=100.0,
        )
        r = run_monte_carlo(state, weeks=4, n=100)
        # No income at all — should have very high deficit probability
        assert r["deficit_probability"] > 50

    def test_monte_carlo_high_income_low_deficit_probability(self):
        state = FakeState(
            jobs=[Job("Well paid", 5000, "Weekly")],
            expenses=[Expense("E", 100, "Bills", "2024-01-01", "Weekly")],
            balance=10_000.0,
        )
        r = run_monte_carlo(state, weeks=4, n=200)
        assert r["deficit_probability"] < 50

    def test_monte_carlo_worst_always_below_best(self, base_state):
        r = run_monte_carlo(base_state, weeks=4, n=50)
        assert r["worst_case"] <= r["best_case"]

    def test_monte_carlo_large_n_completes_quickly(self, base_state):
        import time
        t0 = time.perf_counter()
        run_monte_carlo(base_state, weeks=52, n=500)
        assert time.perf_counter() - t0 < 5.0, "500-run Monte Carlo should finish in under 5s"


# ═════════════════════════════════════════════════════════════════════════════
#  DAY 20 — database.py: dedup_jobs and dedup_expenses
# ═════════════════════════════════════════════════════════════════════════════

class TestDedupJobs:

    def _insert_raw(self, temp_db, rows):
        """Insert (name, amount, frequency) rows directly, bypassing UNIQUE constraint.

        Rebuilds the jobs table without the UNIQUE index so duplicate names
        can be inserted to exercise the dedup logic.
        """
        import sqlite3
        with sqlite3.connect(temp_db) as conn:
            conn.execute("ALTER TABLE jobs RENAME TO _jobs_bak")
            conn.execute(
                "CREATE TABLE jobs ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  name TEXT, amount REAL, frequency TEXT DEFAULT 'Weekly',"
                "  user_id INTEGER DEFAULT 1"
                ")"
            )
            conn.execute(
                "INSERT INTO jobs (id, name, amount, frequency, user_id)"
                " SELECT id, name, amount, frequency, user_id FROM _jobs_bak"
            )
            conn.execute("DROP TABLE _jobs_bak")
            for name, amount, freq in rows:
                conn.execute(
                    "INSERT INTO jobs (name, amount, frequency) VALUES (?, ?, ?)",
                    (name, amount, freq),
                )
            conn.commit()

    def test_identical_names_collapse_to_one(self, temp_db):
        self._insert_raw(temp_db, [
            ("Barista", 300, "Weekly"),
            ("Barista", 200, "Weekly"),
        ])
        database.dedup_jobs()
        assert len(database.load_jobs()) == 1

    def test_highest_amount_is_kept(self, temp_db):
        self._insert_raw(temp_db, [
            ("Barista", 200, "Weekly"),
            ("Barista", 300, "Weekly"),
        ])
        database.dedup_jobs()
        jobs = database.load_jobs()
        assert abs(jobs[0].amount - 300) < 0.01

    def test_case_variants_collapse(self, temp_db):
        self._insert_raw(temp_db, [
            ("admissions", 400, "Weekly"),
            ("Admissions", 500, "Weekly"),
            ("ADMISSIONS", 300, "Weekly"),
        ])
        database.dedup_jobs()
        assert len(database.load_jobs()) == 1

    def test_name_is_canonicalized(self, temp_db):
        self._insert_raw(temp_db, [("admissions", 400, "Weekly")])
        database.dedup_jobs()
        jobs = database.load_jobs()
        assert jobs[0].name == "Admission"

    def test_distinct_jobs_not_merged(self, temp_db):
        self._insert_raw(temp_db, [
            ("Barista", 300, "Weekly"),
            ("Tutor",   200, "Weekly"),
        ])
        database.dedup_jobs()
        assert len(database.load_jobs()) == 2

    def test_no_jobs_does_not_crash(self, temp_db):
        database.dedup_jobs()   # should not raise
        assert database.load_jobs() == []

    def test_single_job_unchanged(self, temp_db):
        self._insert_raw(temp_db, [("Barista", 300, "Weekly")])
        database.dedup_jobs()
        jobs = database.load_jobs()
        assert len(jobs) == 1
        assert abs(jobs[0].amount - 300) < 0.01


class TestDedupExpenses:

    def _insert_raw(self, temp_db, rows):
        """Insert (name, amount, category, date, frequency) rows, bypassing UNIQUE.

        Rebuilds the expenses table without the UNIQUE index so duplicate names
        can be inserted to exercise the dedup logic.
        """
        import sqlite3
        with sqlite3.connect(temp_db) as conn:
            conn.execute("ALTER TABLE expenses RENAME TO _expenses_bak")
            conn.execute(
                "CREATE TABLE expenses ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  name TEXT, amount REAL, category TEXT, date TEXT,"
                "  frequency TEXT DEFAULT 'Monthly',"
                "  user_id INTEGER DEFAULT 1"
                ")"
            )
            conn.execute(
                "INSERT INTO expenses (id, name, amount, category, date, frequency, user_id)"
                " SELECT id, name, amount, category, date, frequency, user_id FROM _expenses_bak"
            )
            conn.execute("DROP TABLE _expenses_bak")
            for name, amount, cat, date, freq in rows:
                conn.execute(
                    "INSERT INTO expenses (name, amount, category, date, frequency)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (name, amount, cat, date, freq),
                )
            conn.commit()

    def test_identical_names_collapse_to_one(self, temp_db):
        self._insert_raw(temp_db, [
            ("Rent", 800, "Housing", "2026-01-01", "Monthly"),
            ("Rent", 900, "Housing", "2026-01-01", "Monthly"),
        ])
        database.dedup_expenses()
        assert len(database.load_expenses()) == 1

    def test_highest_amount_is_kept(self, temp_db):
        self._insert_raw(temp_db, [
            ("Rent", 800, "Housing", "2026-01-01", "Monthly"),
            ("Rent", 900, "Housing", "2026-01-01", "Monthly"),
        ])
        database.dedup_expenses()
        expenses = database.load_expenses()
        assert abs(expenses[0].amount - 900) < 0.01

    def test_case_variants_collapse(self, temp_db):
        self._insert_raw(temp_db, [
            ("rent",  800, "Housing", "2026-01-01", "Monthly"),
            ("Rent",  900, "Housing", "2026-01-01", "Monthly"),
            ("RENT",  700, "Housing", "2026-01-01", "Monthly"),
        ])
        database.dedup_expenses()
        assert len(database.load_expenses()) == 1

    def test_name_is_canonicalized(self, temp_db):
        self._insert_raw(temp_db, [("rents", 800, "Housing", "2026-01-01", "Monthly")])
        database.dedup_expenses()
        expenses = database.load_expenses()
        assert expenses[0].name == "Rent"

    def test_distinct_expenses_not_merged(self, temp_db):
        self._insert_raw(temp_db, [
            ("Rent",  800, "Housing", "2026-01-01", "Monthly"),
            ("Phone",  50, "Bills",   "2026-01-01", "Monthly"),
        ])
        database.dedup_expenses()
        assert len(database.load_expenses()) == 2

    def test_no_expenses_does_not_crash(self, temp_db):
        database.dedup_expenses()
        assert database.load_expenses() == []

    def test_single_expense_unchanged(self, temp_db):
        self._insert_raw(temp_db, [("Rent", 800, "Housing", "2026-01-01", "Monthly")])
        database.dedup_expenses()
        expenses = database.load_expenses()
        assert len(expenses) == 1
        assert abs(expenses[0].amount - 800) < 0.01

    def test_dedup_jobs_and_expenses_independent(self, temp_db):
        # Deduping jobs must not affect expenses and vice versa
        database.insert_job(Job("Barista", 300, "Weekly"))
        self._insert_raw(temp_db, [
            ("Rent", 800, "Housing", "2026-01-01", "Monthly"),
            ("Rent", 900, "Housing", "2026-01-01", "Monthly"),
        ])
        database.dedup_expenses()
        assert len(database.load_jobs()) == 1
        assert abs(database.load_jobs()[0].amount - 300) < 0.01


# ═════════════════════════════════════════════════════════════════════════════
#  DAY 21 — week_engine.py
# ═════════════════════════════════════════════════════════════════════════════

import backend.core.week_engine as we


class TestWeekEngine:

    # ── get_week_start ────────────────────────────────────────────────────────

    def test_week_start_is_monday(self):
        ref   = datetime.date(2026, 6, 17)   # Wednesday
        start = we.get_week_start(ref)
        assert start.weekday() == 0   # 0 = Monday

    def test_week_start_of_monday_is_itself(self):
        monday = datetime.date(2026, 6, 15)
        assert we.get_week_start(monday) == monday

    def test_week_start_of_sunday_is_prev_monday(self):
        sunday = datetime.date(2026, 6, 21)
        assert we.get_week_start(sunday) == datetime.date(2026, 6, 15)

    def test_week_start_year_boundary(self):
        # Jan 1, 2026 is a Thursday — week should start Dec 29, 2025
        d = datetime.date(2026, 1, 1)
        assert we.get_week_start(d) == datetime.date(2025, 12, 29)

    # ── get_previous_week / get_next_week ────────────────────────────────────

    def test_previous_week_is_7_days_before(self):
        monday = datetime.date(2026, 6, 15)
        prev_start, _ = we.get_previous_week(monday)
        assert prev_start == datetime.date(2026, 6, 8)

    def test_next_week_is_7_days_after(self):
        monday = datetime.date(2026, 6, 15)
        next_start, _ = we.get_next_week(monday)
        assert next_start == datetime.date(2026, 6, 22)

    def test_week_span_is_6_days(self):
        monday = datetime.date(2026, 6, 15)
        start, end = we.get_current_week.__wrapped__(monday) if hasattr(we.get_current_week, '__wrapped__') else (monday, monday + datetime.timedelta(days=6))
        assert (end - monday).days == 6

    # ── week_label ────────────────────────────────────────────────────────────

    def test_label_same_month(self):
        s = datetime.date(2026, 6, 15)
        e = datetime.date(2026, 6, 21)
        label = we.week_label(s, e)
        assert "Jun" in label
        assert "15" in label
        assert "21" in label

    def test_label_cross_month(self):
        s = datetime.date(2026, 6, 29)
        e = datetime.date(2026, 7, 5)
        label = we.week_label(s, e)
        assert "Jun" in label
        assert "Jul" in label

    def test_label_cross_year(self):
        s = datetime.date(2025, 12, 29)
        e = datetime.date(2026, 1, 4)
        label = we.week_label(s, e)
        assert "2025" in label
        assert "2026" in label

    # ── day_to_date ───────────────────────────────────────────────────────────

    def test_day_to_date_monday(self):
        monday = datetime.date(2026, 6, 15)
        assert we.day_to_date("Monday", monday) == datetime.date(2026, 6, 15)

    def test_day_to_date_sunday(self):
        monday = datetime.date(2026, 6, 15)
        assert we.day_to_date("Sunday", monday) == datetime.date(2026, 6, 21)

    def test_day_to_date_abbreviation(self):
        monday = datetime.date(2026, 6, 15)
        assert we.day_to_date("Wed", monday) == datetime.date(2026, 6, 17)

    def test_day_to_date_lowercase(self):
        monday = datetime.date(2026, 6, 15)
        assert we.day_to_date("fri", monday) == datetime.date(2026, 6, 19)

    def test_day_to_date_unknown_returns_none(self):
        assert we.day_to_date("Funday", datetime.date(2026, 6, 15)) is None

    # ── date_to_day ───────────────────────────────────────────────────────────

    def test_date_to_day_monday(self):
        assert we.date_to_day(datetime.date(2026, 6, 15)) == "Monday"

    def test_date_to_day_sunday(self):
        assert we.date_to_day(datetime.date(2026, 6, 21)) == "Sunday"

    # ── iso / parse_iso ───────────────────────────────────────────────────────

    def test_iso_format(self):
        assert we.iso(datetime.date(2026, 6, 15)) == "2026-06-15"

    def test_parse_iso_valid(self):
        assert we.parse_iso("2026-06-15") == datetime.date(2026, 6, 15)

    def test_parse_iso_empty_returns_none(self):
        assert we.parse_iso("") is None

    def test_parse_iso_none_returns_none(self):
        assert we.parse_iso(None) is None

    def test_parse_iso_bad_string_returns_none(self):
        assert we.parse_iso("not-a-date") is None

    def test_parse_iso_out_of_range_returns_none(self):
        assert we.parse_iso("2026-13-01") is None

    def test_iso_roundtrip(self):
        d = datetime.date(2026, 6, 15)
        assert we.parse_iso(we.iso(d)) == d

    # ── weeks_for_events ──────────────────────────────────────────────────────

    def test_weeks_for_events_empty(self):
        assert we.weeks_for_events([]) == []

    def test_weeks_for_events_groups_by_week(self):
        events = [
            _make_event(shift_date="2026-06-15"),   # Monday — week of Jun 15
            _make_event(shift_date="2026-06-17"),   # Wednesday — same week
            _make_event(shift_date="2026-06-22"),   # Monday — next week
        ]
        weeks = we.weeks_for_events(events)
        assert len(weeks) == 2
        assert weeks[0] < weeks[1]

    def test_weeks_for_events_skips_no_date(self):
        events = [_make_event(shift_date=""), _make_event(shift_date="2026-06-15")]
        weeks = we.weeks_for_events(events)
        assert len(weeks) == 1

    def test_weeks_for_events_sorted(self):
        events = [
            _make_event(shift_date="2026-06-22"),
            _make_event(shift_date="2026-06-08"),
            _make_event(shift_date="2026-06-15"),
        ]
        weeks = we.weeks_for_events(events)
        assert weeks == sorted(weeks)
