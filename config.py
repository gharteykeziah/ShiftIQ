"""
config.py — Central configuration for ShiftIQ.
Change values here to affect the whole app.
"""

import os

# ── App Info ──────────────────────────────────────────────────────────────────
APP_NAME    = "ShiftIQ"
APP_VERSION = "1.1"

# ── Database ──────────────────────────────────────────────────────────────────
DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "finance.db")

# ── Simulation ────────────────────────────────────────────────────────────────
MONTE_CARLO_RUNS = 500

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.log")
ACTIVITY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "activity.log")

# ── Projection horizons ───────────────────────────────────────────────────────
PROJECTION_WEEKS = [4, 8, 12, 26, 52]

# ── Savings rate thresholds ───────────────────────────────────────────────────
SAVINGS_STRONG   = 0.30   # >= 30%  → health score 90
SAVINGS_GOOD     = 0.20   # >= 20%  → health score 75, risk +20
SAVINGS_OK       = 0.10   # >= 10%  → health score 60, risk +10
SAVINGS_ZERO     = 0.00   # >= 0%   → health score 50

# ── Risk score thresholds ─────────────────────────────────────────────────────
RISK_VERY_STABLE = 80
RISK_STABLE      = 60
RISK_MODERATE    = 40

# ── Expense ratio warning ─────────────────────────────────────────────────────
EXPENSE_RATIO_HIGH    = 0.90   # expenses > 90% of income → high pressure
EXPENSE_RATIO_WARNING = 0.70   # expenses 70–90%          → limited savings
