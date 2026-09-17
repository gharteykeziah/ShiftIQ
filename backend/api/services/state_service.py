"""
services/state_service.py — Financial state summary, balance, history, projection.

Moved verbatim out of api.py's get_state_summary()/update_balance()/get_history()/get_projection().
These back routers/system.py — the endpoints outside the 7 named domains
(auth/jobs/shifts/expenses/optimizer/simulation/insights).
"""
from __future__ import annotations

from fastapi import HTTPException

import backend.core.database as db
from backend.core.dependencies import get_state
from backend.core.schemas import StateSummary


def get_state_summary(user_id: int) -> StateSummary:
    state = get_state(user_id)
    return StateSummary(
        balance=state.current_balance(),
        weekly_income=round(state.total_income_per_week(), 2),
        weekly_expenses=round(state.total_expense_per_week(), 2),
        net_weekly_flow=round(state.net_weekly_flow(), 2),
        savings_rate=round(state.savings_rate(), 4),
        risk_score=state.risk_score(),
        health_score=state.financial_health_score(),
    )


def update_balance(user_id: int, amount: float) -> dict:
    state = get_state(user_id)
    ok, message = state.set_balance(amount)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"balance": amount, "message": message}


def get_history(user_id: int) -> dict:
    """Return all daily financial snapshots ordered by date ascending."""
    snapshots = db.load_history(user_id=user_id)
    return {
        "count": len(snapshots),
        "snapshots": snapshots,
    }


def get_projection(user_id: int, weeks: int) -> dict:
    """Project balance week-by-week over the next N weeks (default 12)."""
    if weeks < 1 or weeks > 520:
        raise HTTPException(status_code=400, detail="weeks must be between 1 and 520.")
    state = get_state(user_id)
    timeline = [
        {"week": w, "balance": round(state.project_balance(w), 2)}
        for w in range(1, weeks + 1)
    ]
    return {
        "weeks": weeks,
        "starting_balance": state.current_balance(),
        "net_weekly_flow": round(state.net_weekly_flow(), 2),
        "timeline": timeline,
    }
