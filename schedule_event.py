"""
schedule_event.py — Event data model for the Time & Income Planner.

An event represents any time block: a work shift, class, study session,
meeting, personal appointment, etc.
"""
from dataclasses import dataclass, field

# ── Constants ─────────────────────────────────────────────────────────────────
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

CATEGORIES = ["Work", "Class", "Study", "Meeting", "Personal", "Other"]

# Color per category (used by the Schedule page for visual coding)
CATEGORY_COLORS = {
    "Work":     "#1B6B3A",   # ShiftIQ accent green
    "Class":    "#2563EB",   # blue
    "Study":    "#D97706",   # amber
    "Meeting":  "#7C3AED",   # purple
    "Personal": "#0891B2",   # teal
    "Other":    "#6B7280",   # grey
}


# ── Time helpers ──────────────────────────────────────────────────────────────
def to_minutes(time_str: str) -> int:
    """Convert "HH:MM" to minutes-since-midnight (0–1439)."""
    h, m = map(int, time_str.split(":"))
    return h * 60 + m


def from_minutes(mins: int) -> str:
    """Convert minutes-since-midnight to "HH:MM" string."""
    return f"{mins // 60:02d}:{mins % 60:02d}"


def fmt_time(time_str: str) -> str:
    """Format "HH:MM" as "H:MM AM/PM" for display."""
    h, m = map(int, time_str.split(":"))
    ampm = "AM" if h < 12 else "PM"
    h12  = h % 12 or 12
    return f"{h12}:{m:02d} {ampm}"


def fmt_duration(hours: float) -> str:
    """Format a decimal hours value as "Xh Ym" or "Xh"."""
    total_mins = round(hours * 60)
    h, m = divmod(total_mins, 60)
    if m:
        return f"{h}h {m}m"
    return f"{h}h"


# ── Data model ────────────────────────────────────────────────────────────────
@dataclass
class ScheduleEvent:
    """One scheduled time block in the planner."""
    title:       str
    category:    str   = "Other"
    day:         str   = "Monday"
    start_time:  str   = "09:00"   # "HH:MM" 24-hour
    end_time:    str   = "10:00"   # "HH:MM" 24-hour
    hourly_rate: float = 0.0       # only meaningful when category == "Work"
    notes:       str   = ""
    id:          int   = 0         # set by database on insert
    shift_date:  str   = ""        # ISO "YYYY-MM-DD"; empty for legacy events

    # ── Derived properties ────────────────────────────────────────────────
    def duration_hours(self) -> float:
        """Length of the event in decimal hours."""
        start = to_minutes(self.start_time)
        end   = to_minutes(self.end_time)
        return max(0.0, (end - start) / 60)

    def income(self) -> float:
        """Estimated income for this event (Work only)."""
        if self.category != "Work" or self.hourly_rate <= 0:
            return 0.0
        return round(self.duration_hours() * self.hourly_rate, 2)

    def display_time(self) -> str:
        """Human-readable time range, e.g. '9:00 AM – 12:00 PM (3h)'."""
        dur = fmt_duration(self.duration_hours())
        return f"{fmt_time(self.start_time)} – {fmt_time(self.end_time)}  ({dur})"

    def color(self) -> str:
        """Background/accent color for this category."""
        return CATEGORY_COLORS.get(self.category, CATEGORY_COLORS["Other"])

    # ── Validation ────────────────────────────────────────────────────────
    def validate(self) -> tuple[bool, str]:
        """Return (ok, message). ok=False means the event should not be saved."""
        if not self.title.strip():
            return False, "Title cannot be empty."
        if self.category not in CATEGORIES:
            return False, f"Category must be one of: {', '.join(CATEGORIES)}."
        if self.day not in DAYS:
            return False, f"Day must be one of: {', '.join(DAYS)}."
        start = to_minutes(self.start_time)
        end   = to_minutes(self.end_time)
        if end <= start:
            return False, "End time must be after start time."
        if self.category == "Work" and self.hourly_rate < 0:
            return False, "Hourly rate cannot be negative."
        return True, "OK"
