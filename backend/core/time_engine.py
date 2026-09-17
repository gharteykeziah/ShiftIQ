"""
time_engine.py — Scheduling analysis algorithms for the Time & Income Planner.

All functions operate on lists of ScheduleEvent objects.  No GUI or database
code lives here — this module is pure logic so it can be tested in isolation.

Public API
──────────
    get_free_blocks(events, day_start, day_end)
        Find all unscheduled time gaps within a day window for a single day's
        events.  Returns a list of {"start", "end", "duration_hours"} dicts.

    largest_free_block(events, day_start, day_end)
        Convenience wrapper — returns just the single longest free block for
        the day, or None if the day is fully booked.

    weekly_availability(all_events, day_start, day_end)
        Aggregate free vs. scheduled hours across the whole week.
        Returns {"scheduled_hours", "free_hours", "availability_pct",
                 "total_window_hours"}.

    detect_conflicts(new_event, existing_events)
        Return any existing events whose time range overlaps new_event on the
        same day.  Returns an empty list when there are no conflicts.

    weekly_income_summary(all_events)
        Sum earnings across all Work-category events.
        Returns {"total_work_hours", "total_income", "by_job"}.

    opportunity_cost(free_block, jobs_with_rates)
        For a single free block and a list of (job_name, hourly_rate) pairs,
        compute potential earnings if each job filled that block.
        Returns a list sorted by potential income, highest first.

Dependencies
────────────
    schedule_event — ScheduleEvent dataclass, DAYS constant, and the
                     to_minutes / from_minutes / fmt_time time helpers.
"""
from __future__ import annotations

from backend.core.schedule_event import ScheduleEvent, DAYS, to_minutes, from_minutes
from backend.core.config import DAY_START as _DAY_START, DAY_END as _DAY_END


# ── Free time analysis ────────────────────────────────────────────────────────

def _free_gaps(
    busy: list[tuple[int, int]],
    start_min: int,
    end_min: int,
) -> list[tuple[int, int]]:
    """
    Core gap-finding algorithm — single source of truth for free-time logic.

    Parameters
    ----------
    busy      : raw (start, end) busy intervals in minutes-since-midnight.
                Callers handle domain-specific pre-processing (e.g. clipping
                overnight shifts at midnight) before passing here.
    start_min : active window start in minutes-since-midnight
    end_min   : active window end   in minutes-since-midnight

    Returns a sorted list of (start, end) free-gap tuples, clamped to the
    active window, with overlapping busy intervals merged before gap-finding.
    """
    # Clamp each interval to the active window and drop empties
    clamped: list[tuple[int, int]] = []
    for s, e in busy:
        s = max(s, start_min)
        e = min(e, end_min)
        if s < e:
            clamped.append((s, e))
    clamped.sort()

    # Merge overlapping intervals
    merged: list[tuple[int, int]] = []
    for s, e in clamped:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    # Collect gaps
    gaps: list[tuple[int, int]] = []
    cursor = start_min
    for s, e in merged:
        if cursor < s:
            gaps.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < end_min:
        gaps.append((cursor, end_min))
    return gaps


def get_free_blocks(
    events: list[ScheduleEvent],
    day_start: str = _DAY_START,
    day_end:   str = _DAY_END,
) -> list[dict]:
    """
    Find free (unscheduled) time blocks within a day window.

    Parameters
    ----------
    events    : events for ONE day, any order
    day_start : earliest time to consider  ("HH:MM")
    day_end   : latest  time to consider   ("HH:MM")

    Returns a list of dicts:
        { "start": "HH:MM", "end": "HH:MM", "duration_hours": float }
    sorted by start time.
    """
    busy = [(to_minutes(e.start_time), to_minutes(e.end_time)) for e in events]
    gaps = _free_gaps(busy, to_minutes(day_start), to_minutes(day_end))
    return [
        {
            "start":          from_minutes(s),
            "end":            from_minutes(e),
            "duration_hours": (e - s) / 60,
        }
        for s, e in gaps
    ]


def largest_free_block(
    events: list[ScheduleEvent],
    day_start: str = _DAY_START,
    day_end:   str = _DAY_END,
) -> dict | None:
    """
    Return the single largest free block for the day, or None if fully booked.
    """
    blocks = get_free_blocks(events, day_start, day_end)
    if not blocks:
        return None
    return max(blocks, key=lambda b: b["duration_hours"])


def weekly_availability(
    all_events: list[ScheduleEvent],
    day_start: str = _DAY_START,
    day_end:   str = _DAY_END,
) -> dict:
    """
    Compute weekly totals:
        scheduled_hours  : total hours of scheduled events
        free_hours       : total hours of free blocks
        availability_pct : free / window * 100 (0–100)
    """
    window_mins = to_minutes(day_end) - to_minutes(day_start)   # per day
    total_window = window_mins * 7 / 60   # hours

    scheduled_hours = sum(e.duration_hours() for e in all_events)
    free_hours       = 0.0

    events_by_day: dict[str, list[ScheduleEvent]] = {d: [] for d in DAYS}
    for e in all_events:
        if e.day in events_by_day:
            events_by_day[e.day].append(e)

    for day_events in events_by_day.values():
        for block in get_free_blocks(day_events, day_start, day_end):
            free_hours += block["duration_hours"]

    availability_pct = round(free_hours / total_window * 100) if total_window else 0
    return {
        "scheduled_hours":  round(scheduled_hours, 1),
        "free_hours":        round(free_hours, 1),
        "availability_pct":  availability_pct,
        "total_window_hours": round(total_window, 1),
    }


# ── Conflict detection ────────────────────────────────────────────────────────

def detect_conflicts(
    new_event: ScheduleEvent,
    existing_events: list[ScheduleEvent],
) -> list[ScheduleEvent]:
    """
    Return a list of existing events that overlap with new_event.
    An overlap exists when the intervals share at least one minute.
    """
    ns = to_minutes(new_event.start_time)
    ne = to_minutes(new_event.end_time)
    conflicts = []
    for ev in existing_events:
        if ev.day != new_event.day:
            continue
        if ev.id and ev.id == new_event.id:
            continue   # skip self when editing
        es = to_minutes(ev.start_time)
        ee = to_minutes(ev.end_time)
        # Intervals overlap iff start of one < end of other
        if ns < ee and ne > es:
            conflicts.append(ev)
    return conflicts


# ── Income summary ────────────────────────────────────────────────────────────

def weekly_income_summary(all_events: list[ScheduleEvent]) -> dict:
    """
    Aggregate work income across all events.

    Returns:
        total_work_hours  : float
        total_income      : float
        by_job            : { job_title: { hours, income, rate } }
    """
    by_job: dict[str, dict] = {}
    for ev in all_events:
        if ev.category != "Work":
            continue
        hrs  = ev.duration_hours()
        inc  = ev.income()
        key  = ev.title
        if key not in by_job:
            by_job[key] = {"hours": 0.0, "income": 0.0, "rate": ev.hourly_rate}
        by_job[key]["hours"]  += hrs
        by_job[key]["income"] += inc

    total_hours  = sum(v["hours"]  for v in by_job.values())
    total_income = sum(v["income"] for v in by_job.values())

    return {
        "total_work_hours": round(total_hours, 2),
        "total_income":      round(total_income, 2),
        "by_job":            {k: {kk: round(vv, 2) for kk, vv in v.items()}
                              for k, v in by_job.items()},
    }


# ── Opportunity cost ──────────────────────────────────────────────────────────

def opportunity_cost(
    free_block: dict,
    jobs_with_rates: list[tuple[str, float]],
) -> list[dict]:
    """
    For a free block and a list of (job_name, hourly_rate) pairs, compute
    potential earnings if the block were filled by each job.

    Returns a list of dicts sorted by potential descending:
        { "job": str, "hours": float, "potential_income": float }
    """
    hours = free_block["duration_hours"]
    results = [
        {
            "job":              name,
            "hours":            round(hours, 2),
            "potential_income": round(hours * rate, 2),
        }
        for name, rate in jobs_with_rates
        if rate > 0
    ]
    return sorted(results, key=lambda x: x["potential_income"], reverse=True)
