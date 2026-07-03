from __future__ import annotations

import random
import logging
import numpy as np
from config import MONTE_CARLO_RUNS

logger = logging.getLogger(__name__)

# ============================================================
#  SIMULATION ENGINE
#
#  Two simulations:
#
#  1. simulate_whatif(state, description, dollar_change, weeks)
#     The user defines what happened in their own words and
#     enters the dollar impact themselves. The engine then
#     plays out the next N weeks showing how their balance
#     changes from that point forward.
#
#  2. run_monte_carlo(state, weeks, n=500)
#     Runs 500 different versions of the user's financial life,
#     each with different random real-world events. Returns the
#     most likely outcome, best case, worst case, and the
#     probability of running out of money.
# ============================================================


# ------------------------------------------------------------
# SIMULATION 1: WHAT-IF
#
# The user says what happened and how much it cost or earned.
# Example: "I got sick" with -90 over 4 weeks.
# The event hits in week 1. Every week after, the regular
# income and expenses continue. The result is a week-by-week
# picture of the balance.
# ------------------------------------------------------------
def simulate_whatif(
    state: "FinancialState",
    description: str,
    dollar_change: float,
    weeks: int,
) -> dict[str, object]:
    """
    Simulates a user-defined event and its effect over N weeks.

    Parameters:
        state         — the current FinancialState
        description   — what the user says happened (free text)
        dollar_change — how much money was gained (+) or lost (-)
        weeks         — how many weeks to project forward

    Returns a list of weekly snapshots:
        week      — week number
        balance   — balance at end of that week
        note      — plain-English description of what happened that week
    """
    balance     = state.current_balance()
    weekly_flow = state.net_weekly_flow()
    history     = []

    for week in range(1, weeks + 1):
        if week == 1:
            balance += dollar_change
            direction = f"+${abs(dollar_change):.2f}" if dollar_change >= 0 else f"-${abs(dollar_change):.2f}"
            note = f"{description}  ({direction})"
        else:
            note = "Regular week — normal income and expenses."

        balance += weekly_flow
        balance  = round(balance, 2)

        history.append({
            "week":    week,
            "balance": balance,
            "note":    note
        })

    # Add a plain-English recovery/gain note at the end
    summary = _whatif_summary(dollar_change, weekly_flow)

    logger.info("simulate_whatif: '%s'  $%.2f  %d weeks", description, dollar_change, weeks)
    logger.info("What-If Simulation: \"%s\"  ($%+.2f over %d weeks)", description, dollar_change, weeks)
    return {
        "history": history,
        "summary": summary
    }


def _whatif_summary(dollar_change: float, weekly_flow: float) -> str:
    """Returns a plain-English sentence about recovery or gain."""
    if dollar_change < 0:
        if weekly_flow > 0:
            recover = abs(dollar_change) / weekly_flow
            return (f"At your current weekly flow, you would recover this "
                    f"${abs(dollar_change):.2f} loss in about {recover:.1f} weeks.")
        else:
            return ("Your weekly flow is zero or negative right now. "
                    "This loss will not recover on its own — consider picking up extra hours "
                    "or cutting an expense.")
    elif dollar_change > 0:
        if weekly_flow > 0:
            equiv = dollar_change / weekly_flow
            return (f"This ${dollar_change:.2f} gain is the equivalent of "
                    f"{equiv:.1f} weeks of your normal savings.")
        else:
            return f"You gained ${dollar_change:.2f}. Consider using it to cover upcoming expenses."
    else:
        return "No dollar impact entered."


# ------------------------------------------------------------
# SIMULATION 2: MONTE CARLO — 500 POSSIBLE FUTURES
#
# Instead of one possible future, this runs 500 versions of
# the user's life simultaneously — each with different random
# real-world events (missed shifts, surprise bills, bonuses,
# etc.). The result shows the range of outcomes and the
# probability of running out of money.
# ------------------------------------------------------------

# Real-life random events used in Monte Carlo only.
# The user does not see or control these — they represent the
# background randomness of everyday life.
_RANDOM_EVENTS = [
    {"name": "Extra shift",           "probability": 0.15, "min":  50,   "max":  200},
    {"name": "Great tips week",       "probability": 0.12, "min":  20,   "max":   90},
    {"name": "Freelance paid out",    "probability": 0.08, "min":  75,   "max":  350},
    {"name": "Friend paid you back",  "probability": 0.07, "min":  20,   "max":  100},
    {"name": "Hours cut by manager",  "probability": 0.10, "min": -180,  "max":  -40},
    {"name": "Called out sick",       "probability": 0.08, "min": -160,  "max":  -50},
    {"name": "Car repair",            "probability": 0.06, "min": -400,  "max":  -80},
    {"name": "Medical copay",         "probability": 0.06, "min": -150,  "max":  -20},
    {"name": "Late fee",              "probability": 0.08, "min":  -75,  "max":  -15},
    {"name": "Groceries over budget", "probability": 0.10, "min":  -60,  "max":  -15},
]


def _roll_random_events() -> float:  # noqa: F811
    """
    Rolls the dice on every background event for one week.

    Kept as a pure-Python reference implementation (used by tests and
    anything that wants a single week's draw); run_monte_carlo() itself
    uses the vectorized NumPy version below for the full N-run / N-week
    simulation, since that loop is the actual performance-sensitive path.
    """
    total = 0.0
    for event in _RANDOM_EVENTS:
        if random.random() < event["probability"]:
            total += round(random.uniform(event["min"], event["max"]), 2)
    return round(total, 2)


# Event parameters hoisted into NumPy arrays once, at import time, so
# run_monte_carlo() never rebuilds them per call.
_EVENT_PROB = np.array([e["probability"] for e in _RANDOM_EVENTS])
_EVENT_MIN  = np.array([e["min"]         for e in _RANDOM_EVENTS], dtype=float)
_EVENT_MAX  = np.array([e["max"]         for e in _RANDOM_EVENTS], dtype=float)


def _roll_random_events_vectorized(n: int, weeks: int) -> np.ndarray:
    """
    Vectorized equivalent of calling _roll_random_events() once per
    (run, week) pair — but drawn for all n*weeks weeks at once via
    NumPy broadcasting instead of a Python for-loop.

    Returns an (n, weeks) array — weekly_totals[i, w] is the net dollar
    effect of background life events in run i, week w.
    """
    num_events = len(_RANDOM_EVENTS)
    shape = (n, weeks, num_events)

    # Which events "hit" this (run, week, event) — same Bernoulli draw
    # _roll_random_events() does, just for every run/week simultaneously.
    hits = np.random.random(shape) < _EVENT_PROB

    # Magnitude for every event slot, regardless of whether it hit —
    # cheaper than drawing only for hits, and statistically identical
    # since we mask non-hits to 0 right after.
    magnitudes = np.random.uniform(_EVENT_MIN, _EVENT_MAX, size=shape)

    return np.sum(hits * magnitudes, axis=2)  # (n, weeks) -> sum over events


def run_monte_carlo(state: "FinancialState", weeks: int, n: int = MONTE_CARLO_RUNS) -> dict[str, object]:
    """
    Runs N simulations of the user's financial life over N weeks.
    Each simulation has different random events each week.

    Vectorized with NumPy: all n runs and all `weeks` weeks of random
    life events are drawn in one batch (see _roll_random_events_vectorized)
    instead of a nested Python for-loop. Same statistical model as the
    original implementation — every event still rolls independently per
    week with the same probability and dollar range — just computed with
    array operations instead of n*weeks individual Python-level dice rolls.

    Returns:
        average             — most likely ending balance
        best_case           — best outcome across all simulations
        worst_case          — worst outcome across all simulations
        deficit_probability — % chance of ending with balance below zero
        safe_probability    — % chance of staying in the positive
        plain_summary       — human-readable paragraph of results
        n                   — number of simulations run
        weeks               — time horizon used
    """
    weekly_flow     = state.net_weekly_flow()
    initial_balance = state.current_balance()

    weekly_event_totals = _roll_random_events_vectorized(n, weeks)               # (n, weeks)
    total_change        = weekly_flow * weeks + weekly_event_totals.sum(axis=1)  # (n,)
    ending_balances_arr = np.round(initial_balance + total_change, 2)
    ending_balances_arr.sort()
    ending_balances = ending_balances_arr.tolist()

    average       = round(sum(ending_balances) / n, 2)
    best_case     = ending_balances[-1]
    worst_case    = ending_balances[0]
    deficit_count = sum(1 for b in ending_balances if b < 0)
    deficit_prob  = round((deficit_count / n) * 100, 1)
    safe_prob     = round(100 - deficit_prob, 1)

    # Percentile helpers (ending_balances is already sorted)
    def _percentile(data, pct):
        idx = (len(data) - 1) * pct / 100
        lo  = int(idx)
        hi  = min(lo + 1, len(data) - 1)
        return round(data[lo] + (data[hi] - data[lo]) * (idx - lo), 2)

    median = _percentile(ending_balances, 50)
    p25    = _percentile(ending_balances, 25)
    p75    = _percentile(ending_balances, 75)

    # Plain-English risk sentence
    if deficit_prob == 0:
        risk = "You have virtually no risk of running out of money in this period."
    elif deficit_prob < 10:
        risk = f"Only {deficit_prob}% of futures ended badly — your finances are in good shape."
    elif deficit_prob < 25:
        risk = (f"{deficit_prob}% of futures ended with you out of money. "
                f"Consider reducing expenses or picking up extra hours.")
    elif deficit_prob < 50:
        risk = (f"{deficit_prob}% of futures ended with you out of money — that's a real risk. "
                f"Your income and expenses need rebalancing.")
    else:
        risk = (f"More than half of all simulated futures ({deficit_prob}%) ended with you out of money. "
                f"Your current financial setup is unstable.")

    plain_summary = (
        f"We ran {n} different versions of your next {weeks} weeks, "
        f"each with different random life events. "
        f"In most futures you end up with ${average:.2f}. "
        f"The best realistic outcome is ${best_case:.2f} and the worst is ${worst_case:.2f}. "
        f"{risk}"
    )

    logger.info("run_monte_carlo: %d runs / %d weeks  avg=$%.2f  deficit=%.1f%%",
                n, weeks, average, deficit_prob)
    logger.info("Monte Carlo Simulation: %d runs over %d weeks (avg $%.2f, %.1f%% deficit risk)",
                n, weeks, average, deficit_prob)
    return {
        "average":             average,
        "best_case":           best_case,
        "worst_case":          worst_case,
        "median":              median,
        "p25":                 p25,
        "p75":                 p75,
        "deficit_probability": deficit_prob,
        "safe_probability":    safe_prob,
        "plain_summary":       plain_summary,
        "ending_balances":     ending_balances,   # raw list for histogram
        "n":                   n,
        "weeks":               weeks
    }
