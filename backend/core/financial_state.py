"""
financial_state.py — Central state manager for ShiftIQ.

Owns all financial data (jobs, expenses, balance) and all calculations.
InsightEngine reads from this — it does not duplicate any logic here.
"""
from __future__ import annotations


import logging
import backend.core.database as db
from backend.core.model import Job, Expense, FREQUENCIES
import backend.core.activity_log as activity_log
from backend.core.config import (
    SAVINGS_STRONG, SAVINGS_GOOD, SAVINGS_OK,
    EXPENSE_RATIO_RISK,
    HEALTH_SCORE_STRONG, HEALTH_SCORE_GOOD, HEALTH_SCORE_OK,
    HEALTH_SCORE_BREAK_EVEN, HEALTH_SCORE_DEFICIT,
    RISK_SCORE_BASELINE, RISK_PENALTY_DEFICIT_FLOW, RISK_PENALTY_HIGH_EXPENSE,
    RISK_BONUS_GOOD_SAVINGS, RISK_BONUS_OK_SAVINGS,
    RISK_PENALTY_NEGATIVE_SAVINGS, RISK_PENALTY_ZERO_BALANCE,
)

# Logging is configured once at startup in main.py / app.py.
# Each module just acquires a named logger — never calls basicConfig.
logger = logging.getLogger(__name__)


class FinancialState:
    """
    Central state manager for ShiftIQ.

    Loads all financial data from the database on construction and exposes
    the full calculation layer — income, expenses, balance, projections,
    scores, and goals — as plain method calls.

    Every number displayed anywhere in the app comes from this class.
    Nothing outside it replicates these calculations.

    Attributes
    ----------
    balance  : current saved balance (float)
    jobs     : list of Job objects (income sources)
    expenses : list of Expense objects
    """

    def __init__(self, user_id: int = 1) -> None:
        """Load all data from the database and record today's snapshot."""
        db.init_db()
        self._user_id = user_id
        self.balance:  float         = db.load_balance(user_id=user_id)
        self.jobs:     list[Job]     = db.load_jobs(user_id=user_id)
        self.expenses: list[Expense] = db.load_expenses(user_id=user_id)
        logger.info(
            "FinancialState initialised — %d jobs, %d expenses, balance $%.2f (user_id=%d)",
            len(self.jobs), len(self.expenses), self.balance, user_id,
        )
        # Record today's snapshot for historical trend tracking
        db.record_snapshot(
            self.balance,
            self.total_income_per_week(),
            self.total_expense_per_week(),
            self.net_weekly_flow(),
            user_id=user_id,
        )

    # ── Validation ────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_job(job: Job) -> tuple[bool, str]:
        """Return (True, '') if valid, or (False, reason) if not."""
        if not job.name or not job.name.strip():
            return False, "Name cannot be blank."
        if job.amount <= 0:
            return False, "Amount must be greater than zero."
        if job.frequency not in FREQUENCIES:
            return False, f"Frequency must be one of: {', '.join(FREQUENCIES)}."
        return True, ""

    @staticmethod
    def _validate_expense(expense: Expense) -> tuple[bool, str]:
        """Return (True, '') if valid, or (False, reason) if not."""
        if not expense.name or not expense.name.strip():
            return False, "Name cannot be blank."
        if expense.amount <= 0:
            return False, "Amount must be greater than zero."
        if not expense.category or not expense.category.strip():
            return False, "Category cannot be blank."
        if expense.frequency not in FREQUENCIES:
            return False, f"Frequency must be one of: {', '.join(FREQUENCIES)}."
        return True, ""

    # ── Jobs ──────────────────────────────────────────────────────────────────

    def add_job(self, job: Job) -> tuple[bool, str]:
        """Add a new income source. Returns (success, message)."""
        ok, reason = self._validate_job(job)
        if not ok:
            logger.warning("add_job validation failed: %s", reason)
            return False, reason
        if any(j.name == job.name for j in self.jobs):
            msg = f"Income source '{job.name}' already exists."
            logger.warning("add_job failed: %s", msg)
            return False, msg
        self.jobs.append(job)
        db.insert_job(job, user_id=self._user_id)
        logger.info("add_job: %s  $%.2f/%s", job.name, job.amount, job.frequency)
        activity_log.log(f"Added Income: {job.name}  (${job.amount:.2f}/{job.frequency})")
        return True, f"'{job.name}' added."

    def delete_job(self, name: str) -> tuple[bool, str]:
        """Remove an income source by name. Returns (success, message)."""
        for job in self.jobs:
            if job.name == name:
                self.jobs.remove(job)
                db.remove_job(name, user_id=self._user_id)
                logger.info("delete_job: %s", name)
                activity_log.log(f"Deleted Income: {name}")
                return True, f"'{name}' deleted."
        msg = f"'{name}' not found."
        logger.warning("delete_job failed: %s", msg)
        return False, msg

    # ── Expenses ──────────────────────────────────────────────────────────────

    def add_expense(self, expense: Expense) -> tuple[bool, str]:
        """Add a new expense. Returns (success, message)."""
        ok, reason = self._validate_expense(expense)
        if not ok:
            logger.warning("add_expense validation failed: %s", reason)
            return False, reason
        if any(e.name == expense.name for e in self.expenses):
            msg = f"Expense '{expense.name}' already exists."
            logger.warning("add_expense failed: %s", msg)
            return False, msg
        self.expenses.append(expense)
        db.insert_expense(expense, user_id=self._user_id)
        logger.info("add_expense: %s  $%.2f/%s  [%s]",
                    expense.name, expense.amount, expense.frequency, expense.category)
        activity_log.log(
            f"Added Expense: {expense.name}  "
            f"(${expense.amount:.2f}/{expense.frequency} — {expense.category})"
        )
        return True, f"Expense '{expense.name}' added."

    def delete_expense(self, name: str) -> tuple[bool, str]:
        """Remove an expense by name. Returns (success, message)."""
        for expense in self.expenses:
            if expense.name == name:
                self.expenses.remove(expense)
                db.remove_expense(name, user_id=self._user_id)
                logger.info("delete_expense: %s", name)
                activity_log.log(f"Deleted Expense: {name}")
                return True, f"Expense '{name}' deleted."
        msg = f"Expense '{name}' not found."
        logger.warning("delete_expense failed: %s", msg)
        return False, msg

    # ── Balance ───────────────────────────────────────────────────────────────

    def set_balance(self, amount: float) -> tuple[bool, str]:
        """Update the current balance and persist it. Returns (success, message)."""
        if not isinstance(amount, (int, float)):
            return False, "Balance must be a number."
        old = self.balance
        self.balance = amount
        db.save_balance(amount, user_id=self._user_id)
        logger.info("set_balance: $%.2f → $%.2f", old, amount)
        activity_log.log(f"Balance Updated: ${old:.2f} → ${amount:.2f}")
        return True, f"Balance updated to ${amount:.2f}."

    def current_balance(self) -> float:
        """Return the current saved balance."""
        return self.balance

    # ── Weekly calculations ───────────────────────────────────────────────────

    def total_income_per_week(self) -> float:
        """Sum of all income sources converted to a weekly amount."""
        return sum(job.weekly_income() for job in self.jobs)

    def total_expense_per_week(self) -> float:
        """Sum of all expenses converted to a weekly amount."""
        return sum(exp.weekly_amount() for exp in self.expenses)

    def net_weekly_flow(self) -> float:
        """Weekly income minus weekly expenses. Positive = surplus."""
        return self.total_income_per_week() - self.total_expense_per_week()

    def savings_rate(self) -> float:
        """Fraction of weekly income saved. 0.0 if no income."""
        income = self.total_income_per_week()
        return self.net_weekly_flow() / income if income else 0.0

    def expense_by_category(self) -> dict[str, float]:
        """
        Weekly expense totals grouped by category.
        Uses weekly_amount() so monthly/daily expenses are correctly converted.
        """
        breakdown: dict[str, float] = {}
        for expense in self.expenses:
            breakdown[expense.category] = (
                breakdown.get(expense.category, 0.0) + expense.weekly_amount()
            )
        return breakdown

    # ── Projections ───────────────────────────────────────────────────────────

    def projected_income(self, weeks: int, scenario: dict | None = None) -> float:
        """
        Total projected income over N weeks, with an optional scenario adjustment.

        scenario dict keys:
          raise_percent — fractional raise on all existing income (0.1 = 10% raise)
          extra_weekly  — flat extra dollars per week added on top of current income

        Both adjustments are applied once to the weekly total, not per job.
        """
        scenario      = scenario or {}
        raise_percent = scenario.get("raise_percent", 0.0)
        extra_weekly  = scenario.get("extra_weekly",  0.0)
        base_income   = self.total_income_per_week()
        weekly_income = base_income * (1 + raise_percent) + extra_weekly
        return weekly_income * weeks

    def projected_expenses(self, weeks: int) -> float:
        """Total projected expenses over N weeks at the current weekly rate."""
        return self.total_expense_per_week() * weeks

    def project_balance(self, weeks: int, scenario: dict | None = None) -> float:
        """Projected balance after N weeks, optionally with a scenario."""
        return (
            self.balance
            + self.projected_income(weeks, scenario)
            - self.projected_expenses(weeks)
        )

    # ── Goals ─────────────────────────────────────────────────────────────────

    def weeks_to_goal(self, goal_amount: float) -> int | None:
        """
        How many weeks to reach goal_amount at current net weekly flow.
        Returns None if flow is zero or negative, or if goal would take
        more than 10,000 weeks (effectively unreachable).
        O(1) formula — replaces the previous O(N) while loop.
        """
        import math
        net = self.net_weekly_flow()
        if net <= 0:
            return None
        remaining = goal_amount - self.balance
        if remaining <= 0:
            return 0
        weeks = math.ceil(remaining / net)
        return weeks if weeks <= 10_000 else None

    def goal_progress(self, goal_amount: float) -> float | None:
        """Percentage of goal_amount already saved. None if goal is zero."""
        if goal_amount == 0:
            return None
        return (self.balance / goal_amount) * 100

    # ── Scores ────────────────────────────────────────────────────────────────

    def financial_health_score(self) -> int:
        """
        Score 0–100 based on savings rate.
        90 = strong (≥30%), 75 = good (≥20%), 60 = ok (≥10%),
        50 = breaking even, 20 = deficit.
        """
        s = self.savings_rate()
        if   s >= SAVINGS_STRONG: return HEALTH_SCORE_STRONG
        elif s >= SAVINGS_GOOD:   return HEALTH_SCORE_GOOD
        elif s >= SAVINGS_OK:     return HEALTH_SCORE_OK
        elif s >= 0:              return HEALTH_SCORE_BREAK_EVEN
        else:                     return HEALTH_SCORE_DEFICIT

    def risk_score(self) -> int:
        """
        Score 0–100. Higher = more financially stable.
        Starts at 50. Adjusts up/down based on flow, expense ratio, savings, balance.
        """
        income   = self.total_income_per_week()
        expenses = self.total_expense_per_week()
        savings  = self.savings_rate()
        score    = RISK_SCORE_BASELINE

        if self.net_weekly_flow() < 0:                          score -= RISK_PENALTY_DEFICIT_FLOW
        if income > 0 and expenses / income > EXPENSE_RATIO_RISK: score -= RISK_PENALTY_HIGH_EXPENSE
        if   savings >= SAVINGS_GOOD:                           score += RISK_BONUS_GOOD_SAVINGS
        elif savings >= SAVINGS_OK:                             score += RISK_BONUS_OK_SAVINGS
        elif savings < 0:                                       score -= RISK_PENALTY_NEGATIVE_SAVINGS
        if self.current_balance() <= 0:                         score -= RISK_PENALTY_ZERO_BALANCE

        return max(0, min(100, score))
