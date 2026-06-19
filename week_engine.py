"""
week_engine.py — Week calculation helpers for the FRE Schedule system.

All week logic lives here so the rest of the codebase stays clean.
A "week" always starts on Monday (weekday index 0) and ends on Sunday.

Public API
──────────
    get_week_start(ref=None)            → datetime.date  (Monday)
    get_current_week()                  → (start, end)
    get_previous_week(week_start)       → (start, end)
    get_next_week(week_start)           → (start, end)
    week_label(start, end)              → "Jun 15 – 21, 2026"
    day_to_date(day_name, week_start)   → datetime.date | None
    date_to_day(d)                      → "Monday"
    iso(d)                              → "2026-06-15"
    parse_iso(s)                        → datetime.date | None
    weeks_for_events(events)            → sorted list of week-start dates
"""
from __future__ import annotations

import datetime

# ── Constants ─────────────────────────────────────────────────────────────────

_DAYS = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]

# All accepted spellings → weekday index (0 = Monday)
_NAME_TO_IDX: dict[str, int] = {}
for _i, _d in enumerate(_DAYS):
    _NAME_TO_IDX[_d.lower()]      = _i   # full name
    _NAME_TO_IDX[_d[:3].lower()]  = _i   # 3-letter abbrev
# Extra common abbreviations
for _abbr, _idx in [("tues", 1), ("weds", 2), ("thur", 3), ("thurs", 3)]:
    _NAME_TO_IDX[_abbr] = _idx


# ── Week boundary helpers ─────────────────────────────────────────────────────

def get_week_start(ref: datetime.date | None = None) -> datetime.date:
    """Return the Monday of the week that contains *ref* (default: today)."""
    d = ref or datetime.date.today()
    return d - datetime.timedelta(days=d.weekday())


def get_current_week() -> tuple[datetime.date, datetime.date]:
    """Return (Monday, Sunday) for the current calendar week."""
    start = get_week_start()
    return start, start + datetime.timedelta(days=6)


def get_previous_week(
    week_start: datetime.date,
) -> tuple[datetime.date, datetime.date]:
    """Return (Monday, Sunday) for the week before *week_start*."""
    start = week_start - datetime.timedelta(weeks=1)
    return start, start + datetime.timedelta(days=6)


def get_next_week(
    week_start: datetime.date,
) -> tuple[datetime.date, datetime.date]:
    """Return (Monday, Sunday) for the week after *week_start*."""
    start = week_start + datetime.timedelta(weeks=1)
    return start, start + datetime.timedelta(days=6)


# ── Display helpers ───────────────────────────────────────────────────────────

def week_label(start: datetime.date, end: datetime.date) -> str:
    """
    Human-readable week range label.

    Same month/year   → "Jun 15 – 21, 2026"
    Different months  → "Jun 29 – Jul 5, 2026"
    Different years   → "Dec 29, 2025 – Jan 4, 2026"
    """
    if start.year == end.year:
        if start.month == end.month:
            return f"{start.strftime('%b %d')} – {end.day}, {end.year}"
        return f"{start.strftime('%b %d')} – {end.strftime('%b %d')}, {end.year}"
    return (
        f"{start.strftime('%b %d, %Y')} – {end.strftime('%b %d, %Y')}"
    )


def is_current_week(week_start: datetime.date) -> bool:
    """True if *week_start* is the Monday of the current calendar week."""
    return week_start == get_week_start()


# ── Day / date conversion ─────────────────────────────────────────────────────

def day_to_date(
    day_name: str,
    week_start: datetime.date,
) -> datetime.date | None:
    """
    Convert a day name ('Monday', 'Mon', 'mon', 'thurs' …) to the actual
    calendar date within the given week.

    Returns None if the day name is not recognised.
    """
    idx = _NAME_TO_IDX.get(day_name.strip().lower())
    if idx is None:
        return None
    return week_start + datetime.timedelta(days=idx)


def date_to_day(d: datetime.date) -> str:
    """Return the canonical full day name for *d* (e.g. 'Wednesday')."""
    return _DAYS[d.weekday()]


# ── ISO helpers ───────────────────────────────────────────────────────────────

def iso(d: datetime.date) -> str:
    """Return the ISO-8601 string 'YYYY-MM-DD' for *d*."""
    return d.isoformat()


def parse_iso(s: str) -> datetime.date | None:
    """
    Parse an ISO-8601 date string to a datetime.date.

    Returns None (never raises) if the string is empty, None, or malformed.
    """
    if not s:
        return None
    try:
        return datetime.date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


# ── History helpers ───────────────────────────────────────────────────────────

def weeks_for_events(events: list) -> list[datetime.date]:
    """
    Given a list of ScheduleEvent objects, return a sorted list of the
    Monday dates representing every week that has at least one event with
    a stored shift_date.

    Events without a shift_date are ignored — they pre-date this feature.
    """
    week_starts: set[datetime.date] = set()
    for ev in events:
        d = parse_iso(getattr(ev, "shift_date", ""))
        if d:
            week_starts.add(get_week_start(d))
    return sorted(week_starts)
