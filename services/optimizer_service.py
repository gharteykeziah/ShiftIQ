"""
services/optimizer_service.py — 0/1 knapsack shift selection.

Moved verbatim out of api.py's optimize_shifts() route body.
"""
from __future__ import annotations

import database as db
from optimizer import candidates_from_events, optimize_shift_selection


def optimize_shifts(user_id: int, max_hours: float) -> dict:
    events = db.get_events(user_id=user_id)
    candidates = candidates_from_events(events)
    result = optimize_shift_selection(candidates, max_hours=max_hours)
    return {
        "selected": [
            {"job_name": c.job_name, "hours": c.hours,
             "hourly_rate": c.hourly_rate, "income": c.income}
            for c in result.selected
        ],
        "total_hours": result.total_hours,
        "total_income": result.total_income,
        "hours_budget": result.hours_budget,
        "hours_unused": result.hours_unused,
        "effective_rate": result.effective_rate,
    }
