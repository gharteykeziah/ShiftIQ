"""
benchmark_monte_carlo.py — Reproducible before/after benchmark for the
NumPy vectorization of run_monte_carlo().

Run it yourself:
    python3 scripts/benchmark_monte_carlo.py

This times the CURRENT (vectorized) implementation in simulation.py and
prints the result. The numbers quoted in README.md were produced by this
same script, run on the same machine, comparing this implementation
against a pure-Python nested-loop version (preserved below for reference
so the comparison is always reproducible, not just asserted).
"""
from __future__ import annotations

import os
import sys
import time
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.simulation import run_monte_carlo, _RANDOM_EVENTS  # noqa: E402


class _FakeState:
    """Minimal stand-in for FinancialState — no DB/GUI needed to benchmark."""
    def __init__(self, balance: float = 1000.0, weekly_flow: float = 100.0):
        self._balance = balance
        self._flow = weekly_flow

    def current_balance(self) -> float:
        return self._balance

    def net_weekly_flow(self) -> float:
        return self._flow


def _roll_random_events_pure_python() -> float:
    """The ORIGINAL (pre-vectorization) per-week dice roll, for comparison."""
    total = 0.0
    for event in _RANDOM_EVENTS:
        if random.random() < event["probability"]:
            total += round(random.uniform(event["min"], event["max"]), 2)
    return round(total, 2)


def run_monte_carlo_pure_python(state, weeks: int, n: int) -> list[float]:
    """The ORIGINAL nested-for-loop Monte Carlo, kept here only to benchmark
    against — this is what run_monte_carlo() used before vectorization."""
    weekly_flow = state.net_weekly_flow()
    ending_balances = []
    for _ in range(n):
        balance = state.current_balance()
        for _ in range(weeks):
            balance += weekly_flow + _roll_random_events_pure_python()
        ending_balances.append(round(balance, 2))
    return ending_balances


def _time_it(fn, repeats: int = 5) -> float:
    """Returns best-of-`repeats` wall time in seconds."""
    best = float("inf")
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    return best


def main() -> None:
    state = _FakeState()
    scenarios = [(500, 52), (500, 12), (5000, 52)]

    print(f"{'Scenario':<22} {'Pure Python':>14} {'NumPy vectorized':>18} {'Speedup':>10}")
    print("-" * 66)
    for n, weeks in scenarios:
        old_t = _time_it(lambda: run_monte_carlo_pure_python(state, weeks, n))
        new_t = _time_it(lambda: run_monte_carlo(state, weeks, n))
        speedup = old_t / new_t if new_t else float("inf")
        label = f"{n} runs / {weeks}wk"
        print(f"{label:<22} {old_t*1000:>11.2f} ms {new_t*1000:>15.2f} ms {speedup:>9.1f}x")


if __name__ == "__main__":
    main()
