"""
test_fre.py — Automated test suite for the ShiftIQ.

Run with:
    python3 -m pytest test_fre.py -v

All tests are self-contained. The database tests use a temporary file —
nothing is written to the real finance.db during testing.
"""

import os
import sys
import pytest

# Make sure we import from the project folder
sys.path.insert(0, os.path.dirname(__file__))

from model import Job, Expense, FREQ_TO_WEEKLY, FREQUENCIES
from insight_engine import InsightEngine
from scenario_engine import ScenarioEngine, Scenario
from simulation import simulate_whatif, run_monte_carlo
import database


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
        from config import SAVINGS_STRONG, SAVINGS_GOOD, SAVINGS_OK
        s = self.savings_rate()
        if   s >= SAVINGS_STRONG: return 90
        elif s >= SAVINGS_GOOD:   return 75
        elif s >= SAVINGS_OK:     return 60
        elif s >= 0:              return 50
        else:                     return 20

    def risk_score(self):
        from config import SAVINGS_GOOD, SAVINGS_OK
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
    """Point database.DB_NAME at a fresh temp file for each test."""
    db_file = str(tmp_path / "test_fre.db")
    monkeypatch.setattr(database, "DB_NAME", db_file)
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

from utils import canon_name, normalize_job_name

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

import shift_analytics as sa
import datetime

def _make_event(title="Job A", category="Work", day="Monday",
                start="09:00", end="17:00", rate=15.0,
                shift_date="2026-06-16", notes=""):
    """Helper — creates a minimal ScheduleEvent-like object."""
    from schedule_event import ScheduleEvent
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

import optimizer as opt


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
