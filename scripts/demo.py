"""
demo.py — ShiftIQ core value prop in 40 lines, no GUI required.

Shows what the engine does with a typical student gig worker's data:
  - Two jobs, one monthly expense load
  - Net flow, savings rate, health and risk scores
  - 4-week and 52-week balance projection
  - What-if: car breaks down, costs $400

Run with:
    python3 scripts/demo.py
"""
import sys, os, tempfile, atexit
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.core.model import Job, Expense
from backend.core.financial_state import FinancialState
from backend.core.simulation import simulate_whatif, run_monte_carlo
from backend.core.insight_engine import InsightEngine

# ── Sample data (a typical campus gig worker) ─────────────────────────────────

import backend.core.database as database
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
database.DB_NAME = _tmp.name   # isolated temp DB — never touches finance.db
atexit.register(os.unlink, _tmp.name)

state = FinancialState()
state.add_job(Job("Campus Dining",  280, "Weekly"))
state.add_job(Job("DoorDash",       150, "Weekly"))
state.add_expense(Expense("Rent",        650, "Housing",   "2026-01-01", "Monthly"))
state.add_expense(Expense("Groceries",   60,  "Food",      "2026-01-01", "Weekly"))
state.add_expense(Expense("Phone",       45,  "Bills",     "2026-01-01", "Monthly"))
state.add_expense(Expense("Transport",   30,  "Transport", "2026-01-01", "Weekly"))
state.set_balance(820.0)

# ── Core numbers ──────────────────────────────────────────────────────────────

engine = InsightEngine()

print("=" * 60)
print("  ShiftIQ — Financial Snapshot")
print("=" * 60)
print(f"  Balance:          ${state.current_balance():.2f}")
print(f"  Weekly income:    ${state.total_income_per_week():.2f}")
print(f"  Weekly expenses:  ${state.total_expense_per_week():.2f}")
print(f"  Net weekly flow:  ${state.net_weekly_flow():.2f}")
print(f"  Savings rate:     {state.savings_rate()*100:.1f}%")
print(f"  Health score:     {state.financial_health_score()} / 100"
      f"  ({engine.health_label(state.financial_health_score())})")
print(f"  Risk score:       {state.risk_score()} / 100"
      f"  ({engine.risk_label(state.risk_score())})")

# ── Projection ────────────────────────────────────────────────────────────────

print()
print("  Projected balance:")
for wks in [4, 8, 26, 52]:
    print(f"    {wks:>2} weeks → ${state.project_balance(wks):.2f}")

# ── Insights ──────────────────────────────────────────────────────────────────

print()
print("  Insights:")
for insight in engine.generate_insights(state):
    print(f"  • {insight}")

# ── What-if ───────────────────────────────────────────────────────────────────

print()
print("  What-if: car breaks down (-$400 this week)")
result = simulate_whatif(state, "Car repair", -400, 4)
for row in result["history"]:
    print(f"    Week {row['week']}: ${row['balance']:.2f}  — {row['note'][:55]}")

# ── Monte Carlo ───────────────────────────────────────────────────────────────

print()
print("  Monte Carlo (200 futures, 12 weeks):")
mc = run_monte_carlo(state, weeks=12, n=200)
print(f"    Average outcome:  ${mc['average']:.2f}")
print(f"    Best case:        ${mc['best_case']:.2f}")
print(f"    Worst case:       ${mc['worst_case']:.2f}")
print(f"    Deficit risk:     {mc['deficit_probability']}%")
print()
