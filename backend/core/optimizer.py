"""
optimizer.py — Constrained shift-selection optimizer for ShiftIQ.

Problem
───────
job_efficiency_report() (schedule_analytics.py) ranks jobs by effective
$/hr — useful, but it's just sorting. It doesn't answer the question a
real variable-income worker actually has:

    "I only have 25 hours free this week. Which combination of
     available shifts should I take to earn the most?"

Sorting by rate and greedily taking the highest-rate shifts first is
NOT guaranteed optimal once an hour budget constrains which shifts can
coexist — a worse-paying short shift can unlock a better total than a
better-paying long one that eats the whole budget. This is the classic
0/1 knapsack problem: each shift is an item with a weight (hours) and a
value (income); the hour budget is the knapsack capacity.

optimize_shift_selection() solves it exactly with dynamic programming,
not a greedy heuristic.

Public API
──────────
    ShiftCandidate                       — one schedulable shift
    OptimizationResult                   — solver output
    optimize_shift_selection(candidates, max_hours) → OptimizationResult
    candidates_from_events(events)       → list[ShiftCandidate]
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ── Hours helper (overnight-aware, mirrors schedule_analytics._shift_hours) ──

def _shift_hours(start_time: str, end_time: str) -> float:
    def _mins(t: str) -> int:
        h, m = map(int, t.split(":"))
        return h * 60 + m

    start = _mins(start_time)
    end   = _mins(end_time)
    if end == start:
        return 0.0
    if end < start:
        end += 1440  # overnight shift
    return round((end - start) / 60, 4)


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ShiftCandidate:
    """One schedulable shift available for the optimizer to choose from."""
    id:          str
    job_name:    str
    hours:       float
    hourly_rate: float

    @property
    def income(self) -> float:
        """Total income this single shift would produce."""
        return round(self.hours * self.hourly_rate, 2)


@dataclass
class OptimizationResult:
    """Output of optimize_shift_selection()."""
    selected:      list[ShiftCandidate] = field(default_factory=list)
    total_hours:   float = 0.0
    total_income:  float = 0.0
    hours_budget:  float = 0.0
    hours_unused:  float = 0.0

    @property
    def effective_rate(self) -> float:
        """Blended $/hr across the selected shifts."""
        if self.total_hours == 0:
            return 0.0
        return round(self.total_income / self.total_hours, 2)


# ── Solver ────────────────────────────────────────────────────────────────────

_QUANTUM_PER_HOUR = 4  # quarter-hour resolution — matches ShiftIQ's scheduling grid


def optimize_shift_selection(
    candidates: list[ShiftCandidate],
    max_hours:  float,
) -> OptimizationResult:
    """
    Choose the subset of `candidates` whose combined hours stay within
    `max_hours` while maximizing combined income.

    Exact 0/1 knapsack solved by dynamic programming:
        weight(i) = hours(i), discretized to quarter-hour units
        value(i)  = income(i)
        capacity  = max_hours, discretized the same way

    Greedy "take the highest $/hr shifts first" is NOT used because it
    can be provably suboptimal under a hard hour cap — e.g. two shifts
    at $14/hr × 6h ($84 total, 12h) can beat one shift at $20/hr × 10h
    ($200 ... but only if 10h fits the budget; once it doesn't, the
    greedy pick loses to a combination greedy would never try).

    Runs in O(n × capacity) time and space, where
    capacity = max_hours × 4 (quarter-hours).

    Returns the optimal OptimizationResult. Deterministic — same input
    always produces the same selection.
    """
    if max_hours <= 0 or not candidates:
        return OptimizationResult(
            selected=[], total_hours=0.0, total_income=0.0,
            hours_budget=max(max_hours, 0.0), hours_unused=max(max_hours, 0.0),
        )

    capacity = round(max_hours * _QUANTUM_PER_HOUR)
    weights  = [max(1, round(c.hours * _QUANTUM_PER_HOUR)) for c in candidates]
    values   = [c.income for c in candidates]
    n        = len(candidates)

    # dp[i][w] = best achievable income using the first i candidates
    #            with total weight <= w (quarter-hours)
    dp: list[list[float]] = [[0.0] * (capacity + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        w_i, v_i = weights[i - 1], values[i - 1]
        row_prev, row_cur = dp[i - 1], dp[i]
        for w in range(capacity + 1):
            best = row_prev[w]
            if w_i <= w:
                take = row_prev[w - w_i] + v_i
                if take > best:
                    best = take
            row_cur[w] = best

    # Reconstruct which candidates were taken
    selected: list[ShiftCandidate] = []
    w = capacity
    for i in range(n, 0, -1):
        if dp[i][w] != dp[i - 1][w]:
            selected.append(candidates[i - 1])
            w -= weights[i - 1]
    selected.reverse()

    total_hours  = round(sum(c.hours for c in selected), 2)
    total_income = round(sum(c.income for c in selected), 2)

    return OptimizationResult(
        selected=selected,
        total_hours=total_hours,
        total_income=total_income,
        hours_budget=max_hours,
        hours_unused=round(max_hours - total_hours, 2),
    )


# ── Adapter: build candidates from real schedule events ──────────────────────

def candidates_from_events(events: list) -> list[ShiftCandidate]:
    """
    Convert a list of ScheduleEvent objects (Work category, with a rate)
    into ShiftCandidate items the optimizer can choose between.

    Non-Work events and events with no rate set are skipped — they are
    not income-bearing shifts and have nothing for the optimizer to do
    with them.
    """
    out: list[ShiftCandidate] = []
    for ev in events:
        if getattr(ev, "category", "") != "Work":
            continue
        rate = getattr(ev, "hourly_rate", 0.0) or 0.0
        if rate <= 0:
            continue
        hours = _shift_hours(ev.start_time, ev.end_time)
        out.append(ShiftCandidate(
            id=str(getattr(ev, "id", id(ev))),
            job_name=ev.title.strip().title(),
            hours=hours,
            hourly_rate=rate,
        ))
    return out
