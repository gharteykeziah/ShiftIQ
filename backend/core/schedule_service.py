"""
schedule_service.py — Business logic for syncing schedule events → financial jobs.

Extracted from app.py so this logic is testable without a Tk window.
Called by app.py on startup and whenever the schedule changes.
"""

from __future__ import annotations
import backend.core.database as db
from backend.core.utils import canon_name
from backend.core.model import Job


def _shift_hours(ev) -> float:
    """
    Hours worked in one event. Handles overnight shifts (end < start).
    Uses to_minutes from schedule_event if available, falls back to manual parse.
    """
    try:
        from backend.core.schedule_event import to_minutes
        s  = to_minutes(ev.start_time)
        e2 = to_minutes(ev.end_time)
    except (ImportError, AttributeError):
        def _parse(t: str) -> int:
            h, m = map(int, t.split(":"))
            return h * 60 + m
        s  = _parse(ev.start_time)
        e2 = _parse(ev.end_time)

    if s == e2:
        return 0.0
    if e2 < s:
        e2 += 1440   # overnight shift
    return round((e2 - s) / 60.0, 4)


def sync_schedule_to_jobs(state) -> int:
    """
    Sum Work event hours per canonical job name, compute weekly income,
    and upsert into state.jobs + DB.

    Returns the number of jobs created or updated.
    Pure business logic — no GUI, no Tk dependency.
    """
    all_work = [
        e for e in db.get_events()
        if e.category == "Work" and e.title.strip()
    ]
    if not all_work:
        return 0

    # Group events by canonical job name
    groups: dict[str, list] = {}
    for ev in all_work:
        key = canon_name(ev.title)
        groups.setdefault(key, []).append(ev)

    # Deduplicate state.jobs by canonical key first
    seen_keys: set[str] = set()
    deduped = []
    for j in state.jobs:
        k = canon_name(j.name)
        if k not in seen_keys:
            seen_keys.add(k)
            deduped.append(j)
    state.jobs[:] = deduped

    updated = 0
    for key, cluster in groups.items():
        total_hours = sum(_shift_hours(e) for e in cluster)
        rates       = [e.hourly_rate for e in cluster if (e.hourly_rate or 0) > 0]
        rate        = rates[0] if rates else 0.0

        # Propagate known rate to sibling events missing it
        if rate > 0:
            db.update_events_rate(key, rate)

        weekly_amount = round(total_hours * rate, 2)

        existing = next(
            (j for j in state.jobs if canon_name(j.name) == key),
            None
        )
        if existing is None:
            new_job = Job(key, weekly_amount, "Weekly")
            if weekly_amount > 0:
                state.add_job(new_job)
            else:
                state.jobs.append(new_job)
                db.insert_job(new_job)
        else:
            existing.name = key
            if weekly_amount > 0:
                existing.amount = weekly_amount
                db.update_job_amount(key, weekly_amount)

        updated += 1

    return updated
