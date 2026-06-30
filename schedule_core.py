"""
schedule_core.py
────────────────
ShiftIQ — Schedule & Time Intelligence Module

A production-style backend for students and part-time workers with
variable weekly schedules. No GUI. No auto-switching. No clutter.

STRUCTURE
─────────
  Database     — SQLite setup, raw insert/select helpers
  Validator    — all input checks before anything touches the DB
  Engine       — core logic: conflicts, free time, income
  Scheduler    — public API: add_job, add_shift, get_weekly_schedule
  Display      — four separate output modes (user picks one)

MODES (call separately — never combined automatically)
─────────────────────────────────────────────────────
  ScheduleMode    — full weekly view, no money, no analysis
  FreeTimeMode    — free blocks only  (show_potential=True adds earning potential)
  OpportunityMode — full per-job earning breakdown for every free block

  Income tracking belongs in the ShiftIQ Jobs/financial module, not here.
  This module is about TIME — when you work and when you're free.

USAGE
─────
  from schedule_core import Scheduler, ScheduleMode, FreeTimeMode, OpportunityMode

  sched = Scheduler()
  sched.add_job("Admissions", hourly_rate=12.50)
  sched.add_shift("Admissions", "Monday", "09:00", "12:00")

  FreeTimeMode(sched).display()
"""
from __future__ import annotations


import sqlite3
import os
import re
from dataclasses import dataclass, field


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

# Path to the SQLite database file (same folder as this script)
_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "finance.db")

# The active portion of each day for free-time calculations
_DAY_START = "08:00"
_DAY_END   = "22:00"

# Canonical day order
_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday",
         "Friday", "Saturday", "Sunday"]

# Day abbreviations accepted in add_shift()
_DAY_ALIASES = {
    "mon":   "Monday",    "tue":   "Tuesday",   "wed":   "Wednesday",
    "thu":   "Thursday",  "thur":  "Thursday",  "thurs": "Thursday",
    "fri":   "Friday",    "sat":   "Saturday",  "sun":   "Sunday",
    "tues":  "Tuesday",   "weds":  "Wednesday",
}


# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Job:
    """A job profile — stored once, reused across many shifts."""
    id:          int
    name:        str
    hourly_rate: float


@dataclass
class Shift:
    """One block of scheduled time linked to a job."""
    id:          int
    job_id:      int
    job_name:    str
    hourly_rate: float
    day:         str
    start_time:  str   # "HH:MM"
    end_time:    str   # "HH:MM"

    @property
    def hours(self) -> float:
        """Duration in decimal hours. Handles overnight shifts correctly."""
        return round(_duration_min(self.start_time, self.end_time) / 60, 2)

    @property
    def income(self) -> float:
        """Gross earnings for this shift."""
        return round(self.hours * self.hourly_rate, 2)

    @property
    def overnight(self) -> bool:
        """True if this shift crosses midnight."""
        return _is_overnight(self.start_time, self.end_time)

    @property
    def display_range(self) -> str:
        """Human-readable time range. Overnight shifts show '(+1)' to flag next-day end."""
        overnight_tag = "  (+1 day)" if self.overnight else ""
        return f"{_fmt12(self.start_time)} – {_fmt12(self.end_time)}{overnight_tag}"


@dataclass
class FreeBlock:
    """A gap in the schedule within the active day window."""
    day:   str
    start: str   # "HH:MM"
    end:   str   # "HH:MM"

    @property
    def hours(self) -> float:
        return round((_to_min(self.end) - _to_min(self.start)) / 60, 2)

    @property
    def display_range(self) -> str:
        return f"{_fmt12(self.start)} – {_fmt12(self.end)}"


# ─────────────────────────────────────────────────────────────────────────────
# TIME UTILITIES  (internal — no need to call directly)
# ─────────────────────────────────────────────────────────────────────────────

def _to_min(t: str) -> int:
    """'HH:MM' → minutes since midnight.  '09:30' → 570"""
    h, m = map(int, t.split(":"))
    return h * 60 + m


def _from_min(m: int) -> str:
    """Minutes since midnight → 'HH:MM'.  570 → '09:30'"""
    return f"{m // 60:02d}:{m % 60:02d}"


def _fmt12(t: str) -> str:
    """'HH:MM' (24h) → '9:00 AM' / '2:30 PM'"""
    h, m = map(int, t.split(":"))
    suffix = "AM" if h < 12 else "PM"
    h12    = h % 12 or 12
    return f"{h12}:{m:02d} {suffix}"


def _fmt_hours(decimal_hours: float) -> str:
    """3.5 → '3h 30m'  |  4.0 → '4h'"""
    total = round(decimal_hours * 60)
    h, m  = divmod(total, 60)
    return f"{h}h {m}m" if m else f"{h}h"


def _is_overnight(start: str, end: str) -> bool:
    """Return True if this shift crosses midnight (end is next day)."""
    return _to_min(end) <= _to_min(start)


def _duration_min(start: str, end: str) -> int:
    """
    Duration in minutes, overnight-aware.
    '22:00' → '04:00'  gives 360 min (6h), not a negative number.
    '14:00' → '14:00'  gives 0 (identical times — zero-length, caught by Validator).
    """
    s = _to_min(start)
    e = _to_min(end)
    if s == e:
        return 0        # identical times — caller treats as invalid
    if e < s:
        e += 1440       # end is on the next calendar day
    return e - s


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATOR
# Everything that can go wrong is caught here, BEFORE the database is touched.
# All errors are plain English — no raw Python exceptions leaked to the user.
# ─────────────────────────────────────────────────────────────────────────────

class ValidationError(Exception):
    """Raised when user input fails a business rule."""
    pass


class Validator:

    # ── Job validation ────────────────────────────────────────────────────────

    @staticmethod
    def job_name(name: str) -> str:
        """Return the cleaned name or raise ValidationError."""
        name = name.strip()
        if not name:
            raise ValidationError("Job name cannot be empty.")
        if len(name) > 60:
            raise ValidationError(
                "Job name is too long (max 60 characters)."
            )
        return name

    @staticmethod
    def hourly_rate(rate) -> float:
        """Accept int/float/string; return float or raise ValidationError."""
        try:
            value = float(rate)
        except (TypeError, ValueError):
            raise ValidationError(
                f"Hourly rate must be a number (e.g. 12.50). Got: '{rate}'"
            )
        if value < 0:
            raise ValidationError("Hourly rate cannot be negative.")
        if value > 10_000:
            raise ValidationError(
                "Hourly rate seems unusually high — please double-check."
            )
        return round(value, 2)

    # ── Shift validation ──────────────────────────────────────────────────────

    @staticmethod
    def day(raw: str) -> str:
        """Accept full names or 3-letter abbreviations; return canonical name."""
        cleaned = raw.strip()
        # Full name check (case-insensitive)
        for d in _DAYS:
            if cleaned.lower() == d.lower():
                return d
        # Abbreviation check
        alias = _DAY_ALIASES.get(cleaned.lower())
        if alias:
            return alias
        raise ValidationError(
            f"'{raw}' is not a valid day. "
            f"Use: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday"
        )

    @staticmethod
    def time_str(raw: str, field_name: str = "Time") -> str:
        """Validate 'HH:MM' format and sensible hour/minute values."""
        raw = raw.strip()
        if not re.fullmatch(r"\d{1,2}:\d{2}", raw):
            raise ValidationError(
                f"{field_name} must be in HH:MM format (e.g. 09:30). Got: '{raw}'"
            )
        h, m = map(int, raw.split(":"))
        if h > 23:
            raise ValidationError(
                f"{field_name} hour must be 00–23. Got: {h}"
            )
        if m > 59:
            raise ValidationError(
                f"{field_name} minutes must be 00–59. Got: {m}"
            )
        return f"{h:02d}:{m:02d}"   # normalise to zero-padded form

    @staticmethod
    def time_range(start: str, end: str) -> None:
        """
        Validate a time range.

        Overnight shifts (end < start) are allowed — e.g. 22:00 → 04:00 is
        a valid 6-hour night shift.  The only things we reject are:
          • identical start and end (zero-length)
          • shifts shorter than 15 minutes
        """
        dur = _duration_min(start, end)
        if dur == 0:
            raise ValidationError(
                f"Start and end time are the same ({_fmt12(start)}). "
                f"A shift must have a non-zero duration."
            )
        if dur < 15:
            raise ValidationError(
                f"Shift is only {dur} minutes long — "
                f"minimum shift length is 15 minutes."
            )
        # Let the user know this will cross midnight (helpful, not an error)
        if _is_overnight(start, end):
            # Not an error — just noted.  Display modes will show "(+1 day)".
            pass

    @staticmethod
    def no_conflict(new_start: str, new_end: str,
                    new_day: str, existing: list["Shift"],
                    exclude_id: int | None = None) -> None:
        """
        Raise ValidationError if the new time range overlaps any existing
        shift on the same day.  Overnight shifts are handled correctly by
        extending past-midnight times to > 1440 minutes for comparison.
        """
        ns = _to_min(new_start)
        ne = ns + _duration_min(new_start, new_end)   # always > ns

        for s in existing:
            if s.day != new_day:
                continue
            if exclude_id is not None and s.id == exclude_id:
                continue
            es = _to_min(s.start_time)
            ee = es + _duration_min(s.start_time, s.end_time)
            # Overlap: intervals [ns,ne) and [es,ee) share at least one minute
            if ns < ee and ne > es:
                raise ValidationError(
                    f"Shift overlaps with an existing block on {new_day}: "
                    f"{s.display_range}  ({s.job_name})"
                )


# ─────────────────────────────────────────────────────────────────────────────
# DATABASE LAYER
# Low-level SQLite helpers. The Scheduler class uses these — callers
# should not interact with the database directly.
# ─────────────────────────────────────────────────────────────────────────────

class _Database:
    """Handles all SQLite operations."""

    def __init__(self, db_path: str = _DB_PATH):
        self._path = db_path
        self._init_tables()

    def _connect(self):
        conn = sqlite3.connect(self._path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_tables(self) -> None:
        """Create tables if they don't exist.  Safe to call on every startup."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fre_jobs (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_name    TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                    hourly_rate REAL    NOT NULL DEFAULT 0.0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fre_shifts (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id     INTEGER NOT NULL,
                    day        TEXT    NOT NULL,
                    start_time TEXT    NOT NULL,
                    end_time   TEXT    NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES fre_jobs(id)
                        ON DELETE CASCADE
                )
            """)
            conn.commit()

    # ── Job operations ────────────────────────────────────────────────────────

    def upsert_job(self, name: str, rate: float) -> Job:
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO fre_jobs (job_name, hourly_rate) VALUES (?, ?)
                ON CONFLICT(job_name)
                DO UPDATE SET hourly_rate = excluded.hourly_rate
            """, (name, rate))
            conn.commit()
            row = conn.execute(
                "SELECT id, job_name, hourly_rate FROM fre_jobs "
                "WHERE job_name = ? COLLATE NOCASE", (name,)
            ).fetchone()
        return Job(id=row[0], name=row[1], hourly_rate=row[2])

    def get_job_by_name(self, name: str) -> Job | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, job_name, hourly_rate FROM fre_jobs "
                "WHERE job_name = ? COLLATE NOCASE", (name,)
            ).fetchone()
        if not row:
            return None
        return Job(id=row[0], name=row[1], hourly_rate=row[2])

    def get_all_jobs(self) -> list[Job]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, job_name, hourly_rate FROM fre_jobs "
                "ORDER BY job_name"
            ).fetchall()
        return [Job(id=r[0], name=r[1], hourly_rate=r[2]) for r in rows]

    def delete_job(self, name: str) -> bool:
        """Returns True if a row was deleted."""
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM fre_jobs WHERE job_name = ? COLLATE NOCASE",
                (name,)
            )
            conn.commit()
        return cur.rowcount > 0

    # ── Shift operations ──────────────────────────────────────────────────────

    def insert_shift(self, job_id: int, day: str,
                     start: str, end: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO fre_shifts (job_id, day, start_time, end_time) "
                "VALUES (?, ?, ?, ?)",
                (job_id, day, start, end),
            )
            conn.commit()
        return cur.lastrowid

    def get_shifts(self, day: str | None = None) -> list[Shift]:
        """Return all shifts (or just one day's) ordered by day then start time."""
        sql = """
            SELECT s.id, s.job_id, j.job_name, j.hourly_rate,
                   s.day, s.start_time, s.end_time
            FROM fre_shifts s
            JOIN fre_jobs j ON s.job_id = j.id
        """
        params: tuple = ()
        if day:
            sql    += " WHERE s.day = ?"
            params  = (day,)
        sql += " ORDER BY s.day, s.start_time"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            Shift(
                id=r[0], job_id=r[1], job_name=r[2], hourly_rate=r[3],
                day=r[4], start_time=r[5], end_time=r[6],
            )
            for r in rows
        ]

    def delete_shift(self, shift_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM fre_shifts WHERE id = ?", (shift_id,)
            )
            conn.commit()
        return cur.rowcount > 0

    def clear_shifts(self) -> None:
        """Delete all shifts (jobs are preserved)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM fre_shifts")
            conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# ENGINE
# Pure algorithmic logic.  Receives plain data, returns plain data.
# No database calls.  No display logic.
# ─────────────────────────────────────────────────────────────────────────────

class Engine:
    """
    Core algorithms for the scheduling system.

    All methods are static — no state is stored here.
    Pass the data in, get the results back.
    """

    @staticmethod
    def detect_conflicts(candidate_start: str, candidate_end: str,
                         candidate_day: str,
                         existing_shifts: list[Shift],
                         exclude_id: int | None = None) -> list[Shift]:
        """
        Return any existing shifts that overlap with the candidate range.
        Uses extended minutes so overnight shifts compare correctly.
        Returns an empty list if there are no conflicts.
        """
        cs = _to_min(candidate_start)
        ce = cs + _duration_min(candidate_start, candidate_end)
        conflicts = []
        for s in existing_shifts:
            if s.day != candidate_day:
                continue
            if exclude_id is not None and s.id == exclude_id:
                continue
            es = _to_min(s.start_time)
            ee = es + _duration_min(s.start_time, s.end_time)
            if cs < ee and ce > es:
                conflicts.append(s)
        return conflicts

    @staticmethod
    def compute_free_time(
        shifts_for_day: list[Shift],
        day: str,
        day_start: str = _DAY_START,
        day_end:   str = _DAY_END,
    ) -> list[FreeBlock]:
        """
        Find all unscheduled gaps in a single day, within the active window.

        Overnight shifts are handled by splitting them at midnight:
          - The portion before midnight is counted on the shift's day.
          - The portion after midnight (next day) is ignored here; it will
            appear as a busy block when that next day is processed IF the
            user also adds it to the next day's shift list.

        Steps:
          1. Convert shifts to (start_min, end_min), clamped to window.
             Overnight shifts are clipped at 1440 (midnight).
          2. Merge overlapping intervals.
          3. Find gaps between them.
        """
        start_min = _to_min(day_start)
        end_min   = _to_min(day_end)
        midnight  = 1440

        raw = []
        for s in shifts_for_day:
            s_m = _to_min(s.start_time)
            # Overnight: end wraps past midnight — clip to midnight for this day
            e_m = s_m + _duration_min(s.start_time, s.end_time)
            e_m = min(e_m, midnight)   # never extend past midnight for one day
            # Clamp both ends to the active window
            s_m = max(s_m, start_min)
            e_m = min(e_m, end_min)
            if s_m < e_m:
                raw.append((s_m, e_m))
        raw.sort()

        # Merge overlapping intervals
        merged: list[tuple[int, int]] = []
        for s, e in raw:
            if merged and s <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
            else:
                merged.append((s, e))

        # Find gaps
        free: list[FreeBlock] = []
        cursor = start_min
        for s, e in merged:
            if cursor < s:
                free.append(FreeBlock(
                    day=day,
                    start=_from_min(cursor),
                    end=_from_min(s),
                ))
            cursor = max(cursor, e)
        if cursor < end_min:
            free.append(FreeBlock(
                day=day,
                start=_from_min(cursor),
                end=_from_min(end_min),
            ))
        return free

    @staticmethod
    def opportunity_analysis(
        free_blocks: list[FreeBlock],
        jobs:        list[Job],
    ) -> list[dict]:
        """
        For each free block, calculate potential earnings per job.

        Returns a list of dicts — one per block — sorted by day then start:
            [
              {
                "block":    FreeBlock,
                "options":  [{"job_name": str, "rate": float, "potential": float}, ...],
                "best_job": str,
                "best_earn": float,
              },
              ...
            ]
        Options within each block are sorted by potential earnings, highest first.
        """
        results = []
        rated_jobs = [j for j in jobs if j.hourly_rate > 0]
        for block in free_blocks:
            options = sorted(
                [
                    {
                        "job_name":  j.name,
                        "rate":      j.hourly_rate,
                        "potential": round(block.hours * j.hourly_rate, 2),
                    }
                    for j in rated_jobs
                ],
                key=lambda x: x["potential"],
                reverse=True,
            )
            best = options[0] if options else None
            results.append({
                "block":     block,
                "options":   options,
                "best_job":  best["job_name"]  if best else "—",
                "best_earn": best["potential"] if best else 0.0,
            })
        return results


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULER  (public API)
# This is the main entry point for all write operations.
# Users of this module should interact through Scheduler, not _Database.
# ─────────────────────────────────────────────────────────────────────────────

class Scheduler:
    """
    Public API for the Schedule & Time Intelligence module.

    All write operations go through here.
    All validation runs before any data is written.

    Usage:
        sched = Scheduler()
        sched.add_job("Library", hourly_rate=11.00)
        sched.add_shift("Library", "Tuesday", "13:00", "16:00")
        schedule = sched.get_weekly_schedule()
    """

    def __init__(self, db_path: str = _DB_PATH):
        self._db  = _Database(db_path)
        self._eng = Engine()

    # ── Job management ────────────────────────────────────────────────────────

    def add_job(self, job_name: str, hourly_rate: float) -> Job:
        """
        Add a new job profile (or update the hourly rate if it already exists).

        Parameters
        ----------
        job_name     : e.g. "Admissions"
        hourly_rate  : e.g. 12.50

        Returns the saved Job object.
        Raises ValidationError on bad input.
        """
        name = Validator.job_name(job_name)
        rate = Validator.hourly_rate(hourly_rate)
        return self._db.upsert_job(name, rate)

    def get_jobs(self) -> list[Job]:
        """Return all job profiles, sorted alphabetically."""
        return self._db.get_all_jobs()

    def delete_job(self, job_name: str) -> None:
        """
        Delete a job and all its associated shifts.
        Raises ValidationError if the job doesn't exist.
        """
        name = Validator.job_name(job_name)
        if not self._db.delete_job(name):
            raise ValidationError(
                f"Job '{name}' not found. "
                f"Check spelling or use get_jobs() to see available jobs."
            )

    # ── Shift management ──────────────────────────────────────────────────────

    def add_shift(self, job_name: str, day: str,
                  start_time: str, end_time: str) -> Shift:
        """
        Add a shift to the current week.

        Parameters
        ----------
        job_name   : must match an existing job profile
        day        : "Monday"–"Sunday" (or abbreviation Mon–Sun)
        start_time : "HH:MM"  24-hour format
        end_time   : "HH:MM"  24-hour format

        Returns the saved Shift object.
        Raises ValidationError on any problem (bad time, conflict, missing job, etc.)
        """
        # Step 1 — validate each field individually
        cleaned_day   = Validator.day(day)
        cleaned_start = Validator.time_str(start_time, "Start time")
        cleaned_end   = Validator.time_str(end_time,   "End time")
        Validator.time_range(cleaned_start, cleaned_end)

        # Step 2 — confirm the job exists
        job = self._db.get_job_by_name(job_name)
        if job is None:
            available = ", ".join(j.name for j in self._db.get_all_jobs())
            hint = f"Available jobs: {available}" if available else \
                   "No jobs exist yet — add one with add_job() first."
            raise ValidationError(
                f"Job '{job_name}' not found.  {hint}"
            )

        # Step 3 — check for scheduling conflicts
        existing = self._db.get_shifts(day=cleaned_day)
        Validator.no_conflict(cleaned_start, cleaned_end,
                              cleaned_day, existing)

        # Step 4 — write to database
        shift_id = self._db.insert_shift(
            job.id, cleaned_day, cleaned_start, cleaned_end
        )
        return Shift(
            id=shift_id, job_id=job.id, job_name=job.name,
            hourly_rate=job.hourly_rate, day=cleaned_day,
            start_time=cleaned_start, end_time=cleaned_end,
        )

    def get_weekly_schedule(self) -> dict[str, list[Shift]]:
        """
        Return all shifts grouped by day, sorted by start time.

        Returns a dict with all 7 days as keys.
        Days with no shifts have empty lists.

        Example:
            {
                "Monday":    [Shift(...), Shift(...)],
                "Tuesday":   [],
                "Wednesday": [Shift(...)],
                ...
            }
        """
        all_shifts = self._db.get_shifts()
        schedule: dict[str, list[Shift]] = {day: [] for day in _DAYS}
        for s in all_shifts:
            if s.day in schedule:
                schedule[s.day].append(s)
        return schedule

    def delete_shift(self, shift_id: int) -> None:
        """Delete a shift by its ID. Raises ValidationError if not found."""
        if not self._db.delete_shift(shift_id):
            raise ValidationError(
                f"Shift ID {shift_id} not found."
            )

    def clear_week(self) -> None:
        """Delete all shifts.  Job profiles are not affected."""
        self._db.clear_shifts()

    # ── Read helpers used by display modes ────────────────────────────────────

    def _all_free_blocks(self) -> list[FreeBlock]:
        """Compute free blocks for every day with at least one shift."""
        schedule = self.get_weekly_schedule()
        blocks   = []
        for day in _DAYS:
            day_shifts = schedule[day]
            blocks.extend(
                Engine.compute_free_time(day_shifts, day)
            )
        return blocks


# ─────────────────────────────────────────────────────────────────────────────
# DISPLAY — base class and output helpers
# ─────────────────────────────────────────────────────────────────────────────

_W = 60   # console width for borders


class _DisplayBase:
    """Shared output utilities for all four modes."""

    def __init__(self, scheduler: Scheduler):
        self._sched = scheduler

    # ── Formatting helpers ────────────────────────────────────────────────────

    @staticmethod
    def _rule(char: str = "─") -> str:
        return char * _W

    @staticmethod
    def _header(title: str) -> None:
        print()
        print("═" * _W)
        print(f"  {title}")
        print("═" * _W)

    @staticmethod
    def _section(title: str) -> None:
        print(f"\n  {title.upper()}")
        print("  " + "─" * (_W - 2))

    @staticmethod
    def _row(left: str, right: str = "", indent: int = 4) -> None:
        pad = " " * indent
        if right:
            gap = _W - indent - len(left) - len(right) - 2
            gap = max(gap, 2)
            print(f"{pad}{left}{' ' * gap}{right}")
        else:
            print(f"{pad}{left}")

    @staticmethod
    def _blank() -> None:
        print()

    def display(self) -> None:
        raise NotImplementedError("Subclass must implement display()")


# ─────────────────────────────────────────────────────────────────────────────
# MODE 1 — SCHEDULE MODE
# Purpose: full weekly view. No money. No analysis.
# ─────────────────────────────────────────────────────────────────────────────

class ScheduleMode(_DisplayBase):
    """
    Show the complete weekly schedule — every shift on every day.

    What you see: shift times, job names, shift duration.
    What you do NOT see: earnings, free time, analysis.

    Usage:
        ScheduleMode(sched).display()
    """

    def display(self) -> None:
        schedule = self._sched.get_weekly_schedule()
        has_any  = any(schedule[d] for d in _DAYS)

        self._header("SCHEDULE MODE  ·  Weekly Overview")

        if not has_any:
            self._blank()
            self._row("No shifts scheduled this week.")
            self._row("Add shifts with:  sched.add_shift(...)")
            self._blank()
            print("═" * _W)
            return

        for day in _DAYS:
            shifts = schedule[day]
            if not shifts:
                continue

            # Day header
            self._blank()
            self._row(f"▸ {day.upper()}", indent=2)
            print("  " + "─" * (_W - 2))

            for s in shifts:
                # Example:  09:00 AM – 12:00 PM   Admissions       (3h)
                time_col = s.display_range
                name_col = s.job_name
                dur_col  = f"({_fmt_hours(s.hours)})"

                line = f"{time_col}   {name_col}"
                gap  = max(2, _W - 4 - len(line) - len(dur_col))
                print(f"    {line}{' ' * gap}{dur_col}")

        self._blank()
        print("═" * _W)

        # Summary bar
        all_shifts    = [s for shifts in schedule.values() for s in shifts]
        total_hours   = round(sum(s.hours for s in all_shifts), 2)
        days_with_shifts = sum(1 for d in _DAYS if schedule[d])
        print(
            f"  {days_with_shifts} day(s) scheduled  ·  "
            f"{_fmt_hours(total_hours)} total  ·  "
            f"{len(all_shifts)} shift(s)"
        )
        print("═" * _W)


# ─────────────────────────────────────────────────────────────────────────────
# MODE 2 — FREE TIME MODE
#
# Default:  just your free blocks — nothing else.
# Optional: pass show_potential=True to see what each block could earn.
#
# The two calls:
#   FreeTimeMode(sched).display()                    ← clean, just the time
#   FreeTimeMode(sched).display(show_potential=True) ← adds earning potential
# ─────────────────────────────────────────────────────────────────────────────

class FreeTimeMode(_DisplayBase):
    """
    Show your free time blocks for the week.

    By default: only the time windows — clean, no financial data.
    Set show_potential=True to overlay what each block could earn.

    Usage:
        FreeTimeMode(sched).display()                    # just free time
        FreeTimeMode(sched).display(show_potential=True) # + earning potential
    """

    def run(self) -> dict:
        """
        Return structured free-time data for all 7 days (consumed by the UI).

        Each day maps to:
            shifts           — list of busy-block dicts
            free_blocks      — list of free-block dicts
            total_busy_hours — float
            total_free_hours — float
        """
        schedule = self._sched.get_weekly_schedule()
        result: dict = {}
        for day in _DAYS:
            shifts    = schedule[day]
            free_blks = Engine.compute_free_time(shifts, day)
            result[day] = {
                "shifts": [
                    {
                        "id":          s.id,
                        "job_name":    s.job_name,
                        "hourly_rate": s.hourly_rate,
                        "start_time":  s.start_time,
                        "end_time":    s.end_time,
                        "hours":       s.hours,
                    }
                    for s in shifts
                ],
                "free_blocks": [
                    {"start": b.start, "end": b.end, "hours": b.hours}
                    for b in free_blks
                ],
                "total_busy_hours": round(sum(s.hours for s in shifts), 2),
                "total_free_hours": round(sum(b.hours for b in free_blks), 2),
            }
        return result

    def display(self, show_potential: bool = False) -> None:
        """
        Parameters
        ----------
        show_potential : bool
            False (default) — show free blocks only. Great for planning
                              personal time, rest, study, etc.
            True           — show free blocks AND what each one could earn
                              at your current job rates.
        """
        schedule = self._sched.get_weekly_schedule()
        jobs     = self._sched.get_jobs() if show_potential else []

        title = (
            "FREE TIME  ·  With Earning Potential"
            if show_potential else
            "FREE TIME  ·  Your Available Blocks This Week"
        )
        self._header(title)

        any_shifts = any(schedule[d] for d in _DAYS)
        if not any_shifts:
            self._blank()
            self._row("No shifts entered — your entire week is open.")
            self._row(
                f"Active window:  {_fmt12(_DAY_START)} – {_fmt12(_DAY_END)}  each day."
            )
            self._blank()
            print("═" * _W)
            return

        total_free_hours = 0.0
        total_max_earn   = 0.0
        any_free_found   = False

        for day in _DAYS:
            shifts      = schedule[day]
            free_blocks = Engine.compute_free_time(shifts, day)

            if not free_blocks:
                if shifts:
                    self._blank()
                    self._row(f"▸ {day.upper()}  —  fully booked", indent=2)
                    print("  " + "─" * (_W - 2))
                    self._row("NO FREE TIME AVAILABLE")
                continue

            any_free_found = True
            self._blank()
            self._row(f"▸ {day.upper()}", indent=2)
            print("  " + "─" * (_W - 2))

            for block in free_blocks:
                total_free_hours += block.hours
                dur = _fmt_hours(block.hours)

                # ── Base line: just the time block ────────────────────────────
                self._row(f"{block.display_range}   ({dur})")

                # ── Optional: earning potential per job ───────────────────────
                if show_potential and jobs:
                    analysis = Engine.opportunity_analysis([block], jobs)[0]
                    total_max_earn += analysis["best_earn"]
                    for opt in analysis["options"]:
                        is_best = opt == analysis["options"][0]
                        marker  = "  ★" if is_best else "   "
                        self._row(
                            f"    {marker} {opt['job_name']}",
                            f"${opt['rate']:.2f}/hr → ${opt['potential']:.2f}",
                            indent=4,
                        )
                    self._blank()

        self._blank()
        print("═" * _W)

        if any_free_found:
            window_h = (_to_min(_DAY_END) - _to_min(_DAY_START)) * 7 / 60
            pct      = round(total_free_hours / window_h * 100) if window_h else 0
            summary  = (
                f"  Free time:  {_fmt_hours(total_free_hours)}"
                f"  ·  {pct}% of weekly window"
            )
            if show_potential and jobs:
                summary += f"  ·  Max potential: ${total_max_earn:.2f}"
            print(summary)
        else:
            print("  NO FREE TIME AVAILABLE — week is fully booked.")

        print("═" * _W)


# ─────────────────────────────────────────────────────────────────────────────
# MODE 3 — OPPORTUNITY MODE
#
# Full earning potential analysis. Shows every free block clearly, then
# breaks down what each job could pay for that window.
#
# Use this when you specifically want to analyse earning opportunities.
# For just viewing your free time, use FreeTimeMode instead.
# ─────────────────────────────────────────────────────────────────────────────

class OpportunityMode(_DisplayBase):
    """
    Full earning-potential analysis.

    Shows every free block clearly, then lists what each job could
    pay for that exact window — sorted highest to lowest.

    Distinct from FreeTimeMode(show_potential=True):
      - This mode is for dedicated financial analysis.
      - It shows a per-job breakdown for every single block.
      - It always ends with a weekly maximum summary.

    Usage:
        OpportunityMode(sched).display()
    """

    def run(self) -> dict:
        """
        Return structured opportunity data keyed by day (consumed by the UI).

        Each day maps to a list of free-block dicts:
            start        — "HH:MM"
            end          — "HH:MM"
            hours        — float
            potential    — [{"job", "rate", "potential_income"}, ...]
            best_job     — str
            best_income  — float
        """
        schedule = self._sched.get_weekly_schedule()
        jobs     = self._sched.get_jobs()
        result: dict = {}
        for day in _DAYS:
            shifts    = schedule[day]
            free_blks = Engine.compute_free_time(shifts, day)
            analysis  = Engine.opportunity_analysis(free_blks, jobs) if free_blks else []
            result[day] = [
                {
                    "start":       entry["block"].start,
                    "end":         entry["block"].end,
                    "hours":       entry["block"].hours,
                    "potential": [
                        {
                            "job":              opt["job_name"],
                            "rate":             opt["rate"],
                            "potential_income": opt["potential"],
                        }
                        for opt in entry["options"]
                    ],
                    "best_job":    entry["best_job"],
                    "best_income": entry["best_earn"],
                }
                for entry in analysis
            ]
        return result

    def display(self) -> None:
        schedule = self._sched.get_weekly_schedule()
        jobs     = self._sched.get_jobs()

        self._header("OPPORTUNITY MODE  ·  Full Earning Potential Analysis")

        if not jobs:
            self._blank()
            self._row("No job profiles found.")
            self._row("Add jobs first:  sched.add_job('Job Name', hourly_rate=12.50)")
            self._blank()
            print("═" * _W)
            return

        # Collect all free blocks across the week
        all_free: list[FreeBlock] = []
        for day in _DAYS:
            all_free.extend(Engine.compute_free_time(schedule[day], day))

        if not all_free:
            self._blank()
            self._row("No free blocks this week — schedule is fully booked.")
            self._blank()
            print("═" * _W)
            return

        analysis    = Engine.opportunity_analysis(all_free, jobs)
        total_max   = 0.0
        current_day = ""

        for entry in analysis:
            block = entry["block"]
            total_max += entry["best_earn"]

            # ── Day header ────────────────────────────────────────────────────
            if block.day != current_day:
                current_day = block.day
                self._blank()
                self._row(f"▸ {block.day.upper()}", indent=2)
                print("  " + "─" * (_W - 2))

            # ── Free block — shown clearly first ──────────────────────────────
            self._row(
                f"  {block.display_range}",
                f"({_fmt_hours(block.hours)})",
                indent=2,
            )

            # ── Earning breakdown per job ─────────────────────────────────────
            if not entry["options"]:
                self._row("    No job rates available.", indent=4)
            else:
                for i, opt in enumerate(entry["options"]):
                    is_best = i == 0
                    marker  = "★ " if is_best else "  "
                    self._row(
                        f"    {marker}{opt['job_name']}",
                        f"${opt['rate']:.2f}/hr  →  ${opt['potential']:.2f}",
                        indent=4,
                    )

            self._blank()

        # ── Weekly summary ────────────────────────────────────────────────────
        print("═" * _W)
        print(f"  {'RATES ON FILE':30s}", end="")
        for j in jobs:
            print(f"  {j.name}: ${j.hourly_rate:.2f}/hr", end="")
        print()
        print("  " + "─" * (_W - 2))
        self._row("MAXIMUM POTENTIAL THIS WEEK", f"${total_max:.2f}")
        self._row("(if every free block filled at highest available rate)", "")
        print("═" * _W)


# ─────────────────────────────────────────────────────────────────────────────
# MODE 4 — INCOME MODE
#
# Calculates exactly how much you will earn this week from your scheduled
# shifts.  Breaks down earnings per job, then shows a weekly total.
# No free-time data — just the money.
# ─────────────────────────────────────────────────────────────────────────────

class IncomeMode(_DisplayBase):
    """
    Show exactly how much you will earn this week from your scheduled shifts.

    Breaks down earnings per job and shift, then shows total hours,
    total income, and weighted average hourly rate for the week.

    Usage:
        IncomeMode(sched).display()
    """

    def run(self) -> dict:
        """
        Return structured income data (consumed by the UI).

        Returns:
            by_job         — {job_name: {"shifts", "total_hours", "hourly_rate", "income"}}
            total_hours    — float
            total_income   — float
            average_hourly — float
        Shifts inside by_job include: {"day", "start_time", "end_time", "hours"}.
        """
        schedule = self._sched.get_weekly_schedule()
        by_job: dict[str, dict] = {}
        for day in _DAYS:
            for s in schedule[day]:
                if s.job_name not in by_job:
                    by_job[s.job_name] = {
                        "shifts":      [],
                        "total_hours": 0.0,
                        "hourly_rate": s.hourly_rate,
                        "income":      0.0,
                    }
                by_job[s.job_name]["shifts"].append({
                    "day":        s.day,
                    "start_time": s.start_time,
                    "end_time":   s.end_time,
                    "hours":      s.hours,
                })
                by_job[s.job_name]["total_hours"] += s.hours
                by_job[s.job_name]["income"]      += s.income

        for info in by_job.values():
            info["total_hours"] = round(info["total_hours"], 2)
            info["income"]      = round(info["income"],      2)

        total_hours  = round(sum(v["total_hours"] for v in by_job.values()), 2)
        total_income = round(sum(v["income"]      for v in by_job.values()), 2)
        avg_rate     = round(total_income / total_hours, 2) if total_hours else 0.0
        return {
            "by_job":          by_job,
            "total_hours":     total_hours,
            "total_income":    total_income,
            "average_hourly":  avg_rate,
        }

    def display(self) -> None:
        schedule = self._sched.get_weekly_schedule()

        # Aggregate shifts by job name
        by_job: dict[str, dict] = {}
        for day in _DAYS:
            for s in schedule[day]:
                if s.job_name not in by_job:
                    by_job[s.job_name] = {
                        "shifts":      [],
                        "total_hours": 0.0,
                        "hourly_rate": s.hourly_rate,
                        "income":      0.0,
                    }
                by_job[s.job_name]["shifts"].append(s)
                by_job[s.job_name]["total_hours"] += s.hours
                by_job[s.job_name]["income"]      += s.income

        # Round per-job totals
        for info in by_job.values():
            info["total_hours"] = round(info["total_hours"], 2)
            info["income"]      = round(info["income"],      2)

        total_hours  = round(sum(v["total_hours"] for v in by_job.values()), 2)
        total_income = round(sum(v["income"]      for v in by_job.values()), 2)
        avg_rate     = round(total_income / total_hours, 2) if total_hours else 0.0

        self._header("INCOME MODE  ·  This Week's Earnings")

        if not by_job:
            self._blank()
            self._row("No shifts scheduled yet.")
            self._row("Add shifts with:  sched.add_shift(...)")
            self._blank()
            print("═" * _W)
            return

        for job_name, info in sorted(by_job.items()):
            self._blank()
            self._row(f"▸ {job_name}  (${info['hourly_rate']:.2f}/hr)", indent=2)
            print("  " + "─" * (_W - 2))
            for s in info["shifts"]:
                line = f"{s.day:12s}  {s.display_range}"
                self._row(line, f"({_fmt_hours(s.hours)})  →  ${s.income:.2f}")
            self._blank()
            self._row(
                f"Subtotal:  {_fmt_hours(info['total_hours'])}",
                f"${info['income']:.2f}",
            )

        self._blank()
        print("═" * _W)
        self._row("TOTAL HOURS",  _fmt_hours(total_hours))
        self._row("TOTAL INCOME", f"${total_income:.2f}")
        self._row("AVG RATE",     f"${avg_rate:.2f}/hr")
        print("═" * _W)


# ─────────────────────────────────────────────────────────────────────────────
# DEMO — run this file directly to see all four modes
# python schedule_core.py
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    sched = Scheduler()
    sched.clear_week()

    # ── Set up job profiles ───────────────────────────────────────────────────
    print("\nSetting up job profiles...")
    sched.add_job("Admissions",           hourly_rate=12.50)
    sched.add_job("Library",              hourly_rate=11.00)
    sched.add_job("International Office", hourly_rate=15.00)

    # ── Enter this week's shifts ──────────────────────────────────────────────
    print("Entering weekly shifts...")

    shift_data = [
        ("Admissions",           "Monday",    "09:00", "12:00"),
        ("Library",              "Monday",    "13:00", "16:00"),
        ("International Office", "Tuesday",   "10:00", "14:00"),
        ("Admissions",           "Wednesday", "08:00", "11:00"),
        ("Admissions",           "Wednesday", "13:30", "17:00"),
        ("Library",              "Thursday",  "09:00", "13:00"),
        ("International Office", "Friday",    "11:00", "15:00"),
    ]

    for job, day, start, end in shift_data:
        try:
            s = sched.add_shift(job, day, start, end)
            print(f"  ✓  {day:10s}  {start}–{end}  {job}")
        except ValidationError as e:
            print(f"  ✗  {e}")

    # ── Demonstrate error handling ────────────────────────────────────────────
    print("\nDemonstrating error handling...")

    bad_cases = [
        # (job, day, start, end, description)
        ("Admissions", "Monday",    "10:00", "11:00", "overlap"),
        ("Library",    "Monday",    "15:00", "13:00", "end before start"),
        ("Library",    "Monday",    "17:00", "17:10", "too short (10 min)"),
        ("Fake Job",   "Friday",    "07:00", "09:00", "job does not exist"),
        ("Library",    "Monday",    "16:00", "25:00", "invalid hour"),
        ("Admissions", "Moonday",   "09:00", "12:00", "invalid day"),
    ]

    for job, day, start, end, desc in bad_cases:
        try:
            sched.add_shift(job, day, start, end)
            print(f"  ✗  [{desc}] — should have failed but didn't")
        except ValidationError as e:
            print(f"  ✓  Caught [{desc}]:  {e}")

    # ── Run each mode separately ──────────────────────────────────────────────
    print("\n" + "·" * 60)
    input("  Press Enter to view MODE 1 — SCHEDULE MODE ...")
    ScheduleMode(sched).display()

    input("  Press Enter to view MODE 2 — FREE TIME (clean view) ...")
    FreeTimeMode(sched).display()

    input("  Press Enter to view MODE 2b — FREE TIME + earning potential ...")
    FreeTimeMode(sched).display(show_potential=True)

    input("  Press Enter to view MODE 3 — OPPORTUNITY MODE ...")
    OpportunityMode(sched).display()
