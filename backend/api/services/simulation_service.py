"""
services/simulation_service.py — Monte Carlo and what-if projections.

Moved verbatim out of api.py's simulate_monte_carlo()/simulate_what_if().
"""
from __future__ import annotations

from backend.core.dependencies import get_state
from backend.core.simulation import run_monte_carlo, simulate_whatif


def run_monte_carlo_sim(user_id: int, weeks: int, n: int) -> dict:
    state = get_state(user_id)
    result = run_monte_carlo(state, weeks=weeks, n=n)
    result.pop("ending_balances", None)  # large array — omit from default JSON response
    return result


def run_whatif_sim(user_id: int, description: str, dollar_change: float, weeks: int) -> dict:
    state = get_state(user_id)
    return simulate_whatif(state, description, dollar_change, weeks)
