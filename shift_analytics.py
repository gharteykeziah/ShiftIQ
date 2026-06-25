"""
schedule_analytics.py — Date-range income and schedule analytics for ShiftIQ.

All functions are pure: they accept ScheduleEvent lists (from database.py)
and return plain dicts / dataclass instances — no GUI, no DB calls.

Public API
──────────
    income_by_job(events)              → {canon_key: IncomeGroup}
    daily_totals(events)               → {date_str: income_float}
    shifts_per_job(events)             → {canon_key: [ScheduleEvent, ...]}
    date_range_summary(events)         → DateRangeSummary
    weekly_breakdown(events, week_start) → {day_name: income_float}
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from utils import canon_name


# ── Canonical helper — delegates to utils.canon_name() ───────────────────────

def _canon(name: str) -> str:
    """Thin wrapper so internal callers are unchanged."""
    return canon_name(name)


# ── Duration helper (overnight-aware) ────────────────────────────────────────

def _shift_hours(event) -> float:
    """Hours worked in one event. Adds 24 h for overnight shifts (end < start)."""
    def _mins(t: str) -> int:
        h, m = map(int, t.split(":"))
        return h * 60 + m

    start = _mins(event.start_time)
    end   = _mins(event.end_time)
    if end == start:
        return 0.0
    if end < start:
        end += 1440          # overnight
    return round((end - start) / 60, 4)


# ── Output types ──────────────────────────────────────────────────────────────

class IncomeGroup:
    """Aggregated income data for one canonical job name."""
    __slots__ = ("name", "rate", "shifts", "total_hours", "total_income")

    def __init__(self, name: str, rate: float = 0.0) -> None:
        self.name         = name
        self.rate         = rate
        self.shifts:  list = []
        self.total_hours  = 0.0
        self.total_income = 0.0

    def add(self, event) -> None:
        """Incorporate one ScheduleEvent into this group."""
        self.shifts.append(event)
        hours = _shift_hours(event)
        rate  = event.hourly_rate if (event.hourly_rate or 0) > 0 else self.rate
        self.total_hours  = round(self.total_hours  + hours, 4)
        self.total_income = round(self.total_income + hours * rate, 2)

    @property
    def avg_rate(self) -> float:
        """Effective average hourly rate across all shifts."""
        if self.total_hours == 0:
            return 0.0
        return round(self.total_income / self.total_hours, 2)

    def __repr__(self) -> str:
        return (
            f"<IncomeGroup {self.name!r} "
            f"shifts={len(self.shifts)} "
            f"hours={self.total_hours:.1f} "
            f"income=${self.total_income:.2f}>"
        )


class DateRangeSummary:
    """Aggregated overview returned by date_range_summary()."""
    __slots__ = (
        "start", "end", "total_income", "total_hours",
        "work_days", "job_groups", "daily",
    )

    def __init__(self) -> None:
        self.start:        str                     = ""
        self.end:          str                     = ""
        self.total_income: float                   = 0.0
        self.total_hours:  float                   = 0.0
        self.work_days:    int                     = 0
        self.job_groups:   dict[str, IncomeGroup]  = {}
        self.daily:        dict[str, float]        = {}   # {date: income}

    def __repr__(self) -> str:
        return (
            f"<DateRangeSummary {self.start}–{self.end} "
            f"jobs={len(self.job_groups)} "
            f"days={self.work_days} "
            f"income=${self.total_income:.2f}>"
        )


# ── Core analytics functions ──────────────────────────────────────────────────

def income_by_job(events: list) -> dict[str, IncomeGroup]:
    """
    Group Work events by canonical job name.

    Returns {canonical_key: IncomeGroup} sorted by total income descending.
    Non-Work events are ignored.
    """
    groups: dict[str, IncomeGroup] = {}

    for ev in events:
        if getattr(ev, "category", "") != "Work":
            continue
        key = _canon(ev.title)
        if key not in groups:
            groups[key] = IncomeGroup(
                name=ev.title.strip().title(),
                rate=ev.hourly_rate or 0.0,
            )
        elif (ev.hourly_rate or 0) > 0 and groups[key].rate == 0:
            groups[key].rate = ev.hourly_rate
        groups[key].add(ev)

    return dict(
        sorted(groups.items(), key=lambda kv: kv[1].total_income, reverse=True)
    )


def daily_totals(events: list) -> dict[str, float]:
    """
    Return {ISO_date: total_income} for dates that have Work events.

    Only events with a non-empty shift_date are included.
    Sorted by date ascending.
    """
    totals: dict[str, float] = defaultdict(float)
    for ev in events:
        if getattr(ev, "category", "") != "Work":
            continue
        date_s = getattr(ev, "shift_date", "")
        if not date_s:
            continue
        hours  = _shift_hours(ev)
        income = hours * (ev.hourly_rate or 0.0)
        totals[date_s] = round(totals[date_s] + income, 2)

    return dict(sorted(totals.items()))


def shifts_per_job(events: list) -> dict[str, list]:
    """
    Group ALL events (any category) by canonical title.
    Returns {canonical_key: [ScheduleEvent, ...]} sorted by key.
    """
    groups: dict[str, list] = defaultdict(list)
    for ev in events:
        groups[_canon(ev.title)].append(ev)
    return dict(sorted(groups.items()))


def date_range_summary(events: list) -> DateRangeSummary:
    """
    Produce a full DateRangeSummary from a list of ScheduleEvent objects.

    Aggregates income by canonical job, computes daily totals, finds
    the date range covered, and counts unique work days.
    """
    result      = DateRangeSummary()
    groups      = income_by_job(events)
    daily       = daily_totals(events)
    work_days:  set[str] = set()

    result.job_groups = groups
    result.daily      = daily

    for group in groups.values():
        result.total_income = round(result.total_income + group.total_income, 2)
        result.total_hours  = round(result.total_hours  + group.total_hours,  4)
        for ev in group.shifts:
            d = getattr(ev, "shift_date", "")
            if d:
                work_days.add(d)

    # Date range from all events (not just Work)
    dates = [
        getattr(ev, "shift_date", "")
        for ev in events
        if getattr(ev, "shift_date", "")
    ]
    if dates:
        result.start = min(dates)
        result.end   = max(dates)

    result.work_days = len(work_days)
    return result


def weekly_breakdown(
    events:     list,
    week_start: datetime.date,
) -> dict[str, float]:
    """
    For a specific calendar week, return income grouped by day name.

    Returns {"Monday": income, "Tuesday": income, ...} for all 7 days.
    Days with no Work events have income = 0.0.
    """
    _DAYS = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    ]
    breakdown = {day: 0.0 for day in _DAYS}

    for ev in events:
        if getattr(ev, "category", "") != "Work":
            continue
        date_s = getattr(ev, "shift_date", "")
        if not date_s:
            continue
        try:
            d = datetime.date.fromisoformat(date_s)
        except ValueError:
            continue
        ev_week = d - datetime.timedelta(days=d.weekday())
        if ev_week != week_start:
            continue
        day_name = _DAYS[d.weekday()]
        hours    = _shift_hours(ev)
        income   = hours * (ev.hourly_rate or 0.0)
        breakdown[day_name] = round(breakdown[day_name] + income, 2)

    return breakdown


def weekly_income_total(events: list, week_start: datetime.date) -> float:
    """Total income for a single calendar week (convenience wrapper)."""
    return round(sum(weekly_breakdown(events, week_start).values()), 2)


def top_earning_days(
    events: list,
    n:      int = 3,
) -> list[tuple[str, float]]:
    """
    Return the top-N highest-earning individual dates as (date_str, income).
    Sorted descending by income.
    """
    totals = daily_totals(events)
    sorted_days = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    return sorted_days[:n]


# ── Decision Engine ───────────────────────────────────────────────────────────

from dataclasses import dataclass


@dataclass
class ShiftImpact:
    """Result of removing one Work shift from the schedule."""
    hours_lost:               float
    income_lost:              float
    new_weekly_income:        float
    weekly_income_pct_change: float   # negative = income drop
    new_net_flow:             float
    risk_delta:               int     # negative = risk increased
    recommendation:           str


def shift_impact(event, state) -> ShiftImpact:
    """
    Compute the financial impact of removing one Work shift event.

    Pure function — reads state but does NOT mutate it.
    state must implement: total_income_per_week(), total_expense_per_week(),
                          net_weekly_flow(), risk_score().
    """
    hours       = _shift_hours(event)
    rate        = (event.hourly_rate or 0.0)
    income_lost = round(hours * rate, 2)

    current_weekly = state.total_income_per_week()
    new_weekly     = round(current_weekly - income_lost, 2)

    pct_change = (
        (new_weekly - current_weekly) / current_weekly * 100
        if current_weekly else 0.0
    )

    new_net = round(new_weekly - state.total_expense_per_week(), 2)

    # Estimate risk delta without mutating state
    delta_score = 0
    if new_net < 0 and state.net_weekly_flow() >= 0:
        delta_score -= 20   # flipped from surplus to deficit
    elif current_weekly > 0:
        new_ratio = state.total_expense_per_week() / new_weekly if new_weekly > 0 else 1.0
        if new_ratio > 0.8:
            delta_score -= 15

    if new_net < 0:
        rec = "Removing this shift puts you in a weekly deficit. Not recommended."
    elif pct_change < -15:
        rec = (
            f"Removing this shift cuts weekly income by {abs(pct_change):.1f}%. "
            f"Consider replacing it first."
        )
    else:
        rec = (
            f"Removing this shift is manageable. "
            f"You still net ${new_net:.2f}/week."
        )

    return ShiftImpact(
        hours_lost=round(hours, 2),
        income_lost=income_lost,
        new_weekly_income=new_weekly,
        weekly_income_pct_change=round(pct_change, 1),
        new_net_flow=new_net,
        risk_delta=delta_score,
        recommendation=rec,
    )


@dataclass
class JobEfficiency:
    """Efficiency metrics for one canonical job."""
    name:            str
    total_hours:     float
    total_income:    float
    income_per_hour: float
    early_starts:    int    # shifts starting before 08:00
    late_ends:       int    # shifts ending at or after 22:00
    efficiency_note: str


def job_efficiency_report(events: list) -> list[JobEfficiency]:
    """
    Rank jobs by income per hour and flag scheduling friction.

    Returns list of JobEfficiency sorted by income_per_hour descending.
    Only Work events are considered.
    """
    groups = income_by_job(events)
    results = []

    for key, group in groups.items():
        early = sum(
            1 for ev in group.shifts
            if int(ev.start_time.split(":")[0]) < 8
        )
        late = sum(
            1 for ev in group.shifts
            if int(ev.end_time.split(":")[0]) >= 22
        )
        iph = group.avg_rate

        if early > 0 and late > 0:
            note = f"High friction: {early} early start(s), {late} late end(s)."
        elif early > 0:
            note = f"{early} early-morning shift(s). Good pay but high scheduling cost."
        elif late > 0:
            note = f"{late} late shift(s). Consider impact on rest and study time."
        else:
            note = "Favorable scheduling pattern."

        results.append(JobEfficiency(
            name=group.name,
            total_hours=group.total_hours,
            total_income=group.total_income,
            income_per_hour=iph,
            early_starts=early,
            late_ends=late,
            efficiency_note=note,
        ))

    return sorted(results, key=lambda j: j.income_per_hour, reverse=True)
