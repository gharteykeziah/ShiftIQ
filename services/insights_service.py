"""
services/insights_service.py — Plain-English insights and schedule analytics.

Moved verbatim out of api.py's get_insights()/analytics_income()/analytics_efficiency().
The InsightEngine() singleton is instantiated once at import time here, same
as it was in api.py at module load.
"""
from __future__ import annotations

import database as db
import shift_analytics as sa
from dependencies import get_state
from insight_engine import InsightEngine

_insight_engine = InsightEngine()


def get_insights(user_id: int) -> dict:
    state = get_state(user_id)
    insights = _insight_engine.generate_insights(state)
    return {
        "health_score": state.financial_health_score(),
        "risk_score": state.risk_score(),
        "health_label": _insight_engine.health_label(state.financial_health_score()),
        "risk_label": _insight_engine.risk_label(state.risk_score()),
        "insights": insights,
    }


def get_income_analytics(user_id: int) -> dict:
    events = db.get_events(user_id=user_id)
    groups = sa.income_by_job(events)
    return {
        key: {
            "name": g.name, "rate": g.rate, "total_hours": g.total_hours,
            "total_income": g.total_income, "avg_rate": g.avg_rate,
            "shift_count": len(g.shifts),
        }
        for key, g in groups.items()
    }


def get_efficiency_analytics(user_id: int) -> list[dict]:
    events = db.get_events(user_id=user_id)
    report = sa.job_efficiency_report(events)
    return [
        {
            "name": j.name, "total_hours": j.total_hours,
            "total_income": j.total_income, "income_per_hour": j.income_per_hour,
            "early_starts": j.early_starts, "late_ends": j.late_ends,
            "efficiency_note": j.efficiency_note,
        }
        for j in report
    ]
