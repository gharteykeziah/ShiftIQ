"""
config.py — Central configuration for ShiftIQ.
Change values here to affect the whole app.
"""

import os

# ── App Info ──────────────────────────────────────────────────────────────────
APP_NAME    = "ShiftIQ"
APP_VERSION = "1.1"

# ── CORS (frontend origins allowed to call the API) ──────────────────────────
# Comma-separated list of allowed origins, e.g.:
#   CORS_ORIGINS=https://app.shiftiq.com,https://staging.shiftiq.com
# Not set (local dev default): allow the standard Next.js dev server origins
# only. Production deployments MUST set this explicitly — the API refuses to
# start with a wildcard origin.
_DEFAULT_DEV_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", _DEFAULT_DEV_ORIGINS).split(",")
    if origin.strip()
]

# ── Database ──────────────────────────────────────────────────────────────────
DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "finance.db")

# ── Schedule window ───────────────────────────────────────────────────────────
DAY_START = "08:00"   # earliest time counted for free-time / shift analysis
DAY_END   = "22:00"   # latest  time counted for free-time / shift analysis

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
EXPENSE_RATIO_RISK    = 0.80   # threshold used inside risk_score()

# ── Financial health score outcomes ───────────────────────────────────────────
HEALTH_SCORE_STRONG     = 90   # savings rate ≥ SAVINGS_STRONG
HEALTH_SCORE_GOOD       = 75   # savings rate ≥ SAVINGS_GOOD
HEALTH_SCORE_OK         = 60   # savings rate ≥ SAVINGS_OK
HEALTH_SCORE_BREAK_EVEN = 50   # savings rate ≥ 0 (breaking even)
HEALTH_SCORE_DEFICIT    = 20   # savings rate < 0 (spending more than earning)

# ── Risk score adjustments ────────────────────────────────────────────────────
RISK_SCORE_BASELINE          = 50   # starting point before adjustments
RISK_PENALTY_DEFICIT_FLOW    = 20   # weekly net flow is negative
RISK_PENALTY_HIGH_EXPENSE    = 15   # expense ratio > EXPENSE_RATIO_RISK
RISK_BONUS_GOOD_SAVINGS      = 20   # savings rate ≥ SAVINGS_GOOD
RISK_BONUS_OK_SAVINGS        = 10   # savings rate ≥ SAVINGS_OK
RISK_PENALTY_NEGATIVE_SAVINGS = 25  # savings rate < 0
RISK_PENALTY_ZERO_BALANCE    = 10   # current balance ≤ 0
