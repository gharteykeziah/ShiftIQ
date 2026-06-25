"""
shift_engine.py — Scheduling backend for the ShiftIQ (ShiftIQ).

Designed for part-time workers with VARIABLE weekly schedules.
Users define job profiles once, then enter new shifts each week.

Database tables
---------------
    jobs          — job profiles (name + hourly rate)
    weekly_shifts — this week's shifts, linked to a job

Three analysis modes (called separately by the user)
-----------------------------------------------------
    FreeTimeMode   — shows busy blocks and free blocks only
    IncomeMode     — calculates how much you will earn this week
    OpportunityMode — estimates what you COULD earn in your free time

No GUI. No notifications. Backend only.
"""
from __future__ import annotations


import sqlite3
import os

# ── Configuration ─────────────────────────────────────────────────────────────
# Change this path if you want a different database file location.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "finance.db")

# The day window we consider "your day" (for free-time calculations).
# Anything outside this range is ignored.
DAY_START = "08:00"   # 8:00 AM
DAY_END   = "22:00"   # 10:00 PM

# The order days appear in output
DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — DATABASE SETUP
# ─────────────────────────────────────────────────────────────────────────────

def init_shift_tables() -> None:
    """
    Create the jobs and weekly_shifts tables if they don't already exist.
    Safe to call every time the app starts — won't overwrite existing data.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                job_name    TEXT    NOT NULL UNIQUE,
                hourly_rate REAL    NOT NULL DEFAULT 0.0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS weekly_shifts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id     INTEGER NOT NULL,
                day        TEXT    NOT NULL,
                start_time TEXT    NOT NULL,   -- stored as "HH:MM" (24-hour)
                end_time   TEXT    NOT NULL,   -- stored as "HH:MM" (24-hour)
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            )
        """)
        conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — JOB PROFILE FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def add_job(job_name: str, hourly_rate: float) -> dict:
    """
    Add a new job profile (or update the rate if the name already exists).

    Parameters
    ----------
    job_name    : e.g. "Admissions", "Library"
    hourly_rate : e.g. 12.50

    Returns the saved job as a dict.
    """
    job_name = job_name.strip()
    if not job_name:
        raise ValueError("Job name cannot be empty.")
    if hourly_rate < 0:
        raise ValueError("Hourly rate cannot be negative.")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO jobs (job_name, hourly_rate)
            VALUES (?, ?)
            ON CONFLICT(job_name) DO UPDATE SET hourly_rate = excluded.hourly_rate
        """, (job_name, hourly_rate))
        conn.commit()
        row = conn.execute(
            "SELECT id, job_name, hourly_rate FROM jobs WHERE job_name = ?",
            (job_name,)
        ).fetchone()

    return {"id": row[0], "job_name": row[1], "hourly_rate": row[2]}


def get_jobs() -> list[dict]:
    """
    Return all saved job profiles, sorted alphabetically.

    Example return value:
        [
            {"id": 1, "job_name": "Admissions", "hourly_rate": 12.50},
            {"id": 2, "job_name": "Library",    "hourly_rate": 11.00},
        ]
    """
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, job_name, hourly_rate FROM jobs ORDER BY job_name"
        ).fetchall()
    return [{"id": r[0], "job_name": r[1], "hourly_rate": r[2]} for r in rows]


def get_job_by_name(job_name: str) -> dict | None:
    """
    Look up a job by name.  Returns None if not found.
    """
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, job_name, hourly_rate FROM jobs WHERE job_name = ?",
            (job_name.strip(),)
        ).fetchone()
    if row is None:
        return None
    return {"id": row[0], "job_name": row[1], "hourly_rate": row[2]}


def delete_job(job_name: str) -> None:
    """
    Delete a job profile AND all its shifts.
    """
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id FROM jobs WHERE job_name = ?", (job_name.strip(),)
        ).fetchone()
        if row:
            conn.execute("DELETE FROM weekly_shifts WHERE job_id = ?", (row[0],))
            conn.execute("DELETE FROM jobs WHERE id = ?",               (row[0],))
            conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — WEEKLY SHIFT FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def add_shift(job_name: str, day: str, start_time: str, end_time: str) -> dict:
    """
    Add one shift to the current week.

    Parameters
    ----------
    job_name   : must match an existing job profile exactly
    day        : "Monday" through "Sunday"
    start_time : "HH:MM"  (24-hour) — e.g. "09:00"
    end_time   : "HH:MM"  (24-hour) — e.g. "12:00"

    Raises ValueError if the job doesn't exist, the day is invalid,
    or end time is not after start time.

    Returns the saved shift as a dict.

    Example
    -------
        add_shift("Admissions", "Monday", "09:00", "12:00")
    """
    # Validate job exists
    job = get_job_by_name(job_name)
    if job is None:
        raise ValueError(
            f"Job '{job_name}' not found. "
            f"Call add_job() first."
        )

    # Validate day
    day = day.strip().capitalize()
    # Fix common abbreviations
    abbrev = {"Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday",
              "Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday"}
    day = abbrev.get(day, day)
    if day not in DAY_ORDER:
        raise ValueError(f"Day must be one of: {', '.join(DAY_ORDER)}")

    # Validate times
    start_m = _time_to_minutes(start_time)
    end_m   = _time_to_minutes(end_time)
    if end_m <= start_m:
        raise ValueError(
            f"End time ({end_time}) must be after start time ({start_time})."
        )

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("""
            INSERT INTO weekly_shifts (job_id, day, start_time, end_time)
            VALUES (?, ?, ?, ?)
        """, (job["id"], day, start_time, end_time))
        conn.commit()
        shift_id = cur.lastrowid

    return {
        "id":         shift_id,
        "job_name":   job["job_name"],
        "hourly_rate": job["hourly_rate"],
        "day":        day,
        "start_time": start_time,
        "end_time":   end_time,
        "hours":      round((end_m - start_m) / 60, 2),
    }


def get_weekly_schedule() -> dict[str, list[dict]]:
    """
    Return all shifts for the week, grouped by day and sorted by start time.

    Return value structure:
        {
            "Monday": [
                {"id": 1, "job_name": "Admissions", "hourly_rate": 12.50,
                 "start_time": "09:00", "end_time": "12:00", "hours": 3.0},
                ...
            ],
            "Tuesday": [...],
            ...
        }
    Days with no shifts are included as empty lists.
    """
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT ws.id, j.job_name, j.hourly_rate,
                   ws.day, ws.start_time, ws.end_time
            FROM weekly_shifts ws
            JOIN jobs j ON ws.job_id = j.id
            ORDER BY ws.day, ws.start_time
        """).fetchall()

    # Build the dict with all 7 days (empty lists for days with no shifts)
    schedule: dict[str, list[dict]] = {day: [] for day in DAY_ORDER}

    for row in rows:
        shift_id, job_name, hourly_rate, day, start_time, end_time = row
        hours = round((_time_to_minutes(end_time) - _time_to_minutes(start_time)) / 60, 2)
        if day in schedule:
            schedule[day].append({
                "id":          shift_id,
                "job_name":    job_name,
                "hourly_rate": hourly_rate,
                "start_time":  start_time,
                "end_time":    end_time,
                "hours":       hours,
            })

    return schedule


def clear_week() -> None:
    """
    Delete ALL shifts for the current week.
    Use this at the start of each new week to enter fresh shifts.
    Job profiles are NOT deleted — only the shifts.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM weekly_shifts")
        conn.commit()


def delete_shift(shift_id: int) -> None:
    """Delete a single shift by its id."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM weekly_shifts WHERE id = ?", (shift_id,))
        conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — TIME UTILITY FUNCTIONS
# (Internal helpers — not meant to be called directly by the user)
# ─────────────────────────────────────────────────────────────────────────────

def _time_to_minutes(time_str: str) -> int:
    """
    Convert a time string like "09:30" into minutes since midnight.
    "09:30"  →  570
    "14:00"  →  840
    """
    h, m = map(int, time_str.strip().split(":"))
    return h * 60 + m


def _minutes_to_time(minutes: int) -> str:
    """
    Convert minutes since midnight back to "HH:MM".
    570  →  "09:30"
    840  →  "14:00"
    """
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _format_time_12h(time_str: str) -> str:
    """
    Convert "HH:MM" (24-hour) to "H:MM AM/PM" for human-readable output.
    "09:00"  →  "9:00 AM"
    "13:30"  →  "1:30 PM"
    """
    h, m = map(int, time_str.split(":"))
    ampm = "AM" if h < 12 else "PM"
    h12  = h % 12 or 12
    return f"{h12}:{m:02d} {ampm}"


def _format_hours(decimal_hours: float) -> str:
    """
    Format a decimal hours value as "Xh Ym" or "Xh".
    3.5   →  "3h 30m"
    4.0   →  "4h"
    """
    total_mins = round(decimal_hours * 60)
    h, m = divmod(total_mins, 60)
    return f"{h}h {m}m" if m else f"{h}h"


def _get_free_blocks(shifts_for_day: list[dict],
                     day_start: str = DAY_START,
                     day_end:   str = DAY_END) -> list[dict]:
    """
    Given a list of shifts for ONE day, find the gaps between them.

    Steps:
    1. Convert all shifts to (start_minutes, end_minutes) pairs.
    2. Sort by start time.
    3. Merge any overlapping shifts into single busy blocks.
    4. Find the gaps between busy blocks.

    Returns a list of free blocks:
        [{"start": "HH:MM", "end": "HH:MM", "hours": float}, ...]
    """
    start_min = _time_to_minutes(day_start)
    end_min   = _time_to_minutes(day_end)

    # Step 1 & 2 — collect and sort occupied intervals
    occupied = sorted(
        [(_time_to_minutes(s["start_time"]),
          _time_to_minutes(s["end_time"])) for s in shifts_for_day]
    )

    # Step 3 — merge overlapping busy blocks
    merged = []
    for s, e in occupied:
        # Clamp to the day window
        s = max(s, start_min)
        e = min(e, end_min)
        if s >= e:
            continue   # shift is entirely outside the day window
        if merged and s <= merged[-1][1]:
            # This shift overlaps the previous block — extend it
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    # Step 4 — find gaps (free blocks) between busy blocks
    free_blocks = []
    cursor = start_min

    for busy_start, busy_end in merged:
        if cursor < busy_start:
            # There is a gap before this busy block
            hours = round((busy_start - cursor) / 60, 2)
            free_blocks.append({
                "start": _minutes_to_time(cursor),
                "end":   _minutes_to_time(busy_start),
                "hours": hours,
            })
        cursor = max(cursor, busy_end)

    # Check for free time after the last busy block
    if cursor < end_min:
        hours = round((end_min - cursor) / 60, 2)
        free_blocks.append({
            "start": _minutes_to_time(cursor),
            "end":   _minutes_to_time(end_min),
            "hours": hours,
        })

    return free_blocks


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — THE THREE MODES
# ─────────────────────────────────────────────────────────────────────────────
# Each mode is a class with two methods:
#   run()     — returns structured data (a dict) for use in code or GUIs
#   display() — prints a human-readable summary to the terminal
#
# IMPORTANT: modes do NOT call each other automatically.
# The user calls the one they need.
# ─────────────────────────────────────────────────────────────────────────────


class FreeTimeMode:
    """
    MODE A: Free Time Mode
    ----------------------
    Shows WHEN you are busy and WHEN you are free.
    No financial data — just your schedule layout.

    Usage:
        mode = FreeTimeMode()
        data = mode.run()     # get the data as a dict
        mode.display()        # print it to the terminal
    """

    def run(self) -> dict:
        """
        Returns a dict keyed by day.  Each day has:
            "shifts"      : list of busy blocks (from your scheduled shifts)
            "free_blocks" : list of free blocks between shifts
            "total_busy_hours" : float
            "total_free_hours" : float

        Example:
            {
                "Monday": {
                    "shifts": [
                        {"job_name": "Admissions",
                         "start_time": "09:00", "end_time": "12:00", "hours": 3.0}
                    ],
                    "free_blocks": [
                        {"start": "12:00", "end": "13:00", "hours": 1.0},
                        {"start": "15:00", "end": "22:00", "hours": 7.0}
                    ],
                    "total_busy_hours": 3.0,
                    "total_free_hours": 8.0,
                },
                ...
            }
        """
        schedule = get_weekly_schedule()
        result   = {}

        for day in DAY_ORDER:
            shifts      = schedule[day]
            free_blocks = _get_free_blocks(shifts)
            busy_hours  = sum(s["hours"] for s in shifts)
            free_hours  = sum(b["hours"] for b in free_blocks)
            result[day] = {
                "shifts":           shifts,
                "free_blocks":      free_blocks,
                "total_busy_hours": round(busy_hours, 2),
                "total_free_hours": round(free_hours, 2),
            }

        return result

    def display(self) -> None:
        """Print a formatted free-time summary to the terminal."""
        data = self.run()

        print("\n" + "=" * 58)
        print("  FREE TIME MODE  —  Your Week at a Glance")
        print("=" * 58)

        total_busy = 0.0
        total_free = 0.0

        for day in DAY_ORDER:
            day_data = data[day]
            busy_h   = day_data["total_busy_hours"]
            free_h   = day_data["total_free_hours"]
            total_busy += busy_h
            total_free += free_h

            print(f"\n  {day}")
            print(f"  {'─' * 50}")

            if not day_data["shifts"] and not day_data["free_blocks"]:
                print("    No data for today.")
                continue

            # Busy blocks
            if day_data["shifts"]:
                for s in day_data["shifts"]:
                    start = _format_time_12h(s["start_time"])
                    end   = _format_time_12h(s["end_time"])
                    print(f"    [BUSY]  {start} – {end}"
                          f"  ({_format_hours(s['hours'])})  ←  {s['job_name']}")
            else:
                print("    No shifts scheduled.")

            # Free blocks
            if day_data["free_blocks"]:
                for b in day_data["free_blocks"]:
                    start = _format_time_12h(b["start"])
                    end   = _format_time_12h(b["end"])
                    print(f"    [FREE]  {start} – {end}"
                          f"  ({_format_hours(b['hours'])})")
            else:
                print("    No free time in day window.")

            print(f"    ── {_format_hours(busy_h)} busy  /  "
                  f"{_format_hours(free_h)} free")

        print(f"\n{'=' * 58}")
        print(f"  WEEK TOTAL:  {_format_hours(total_busy)} busy  |  "
              f"{_format_hours(total_free)} free")
        window_h = (_time_to_minutes(DAY_END) - _time_to_minutes(DAY_START)) * 7 / 60
        avail_pct = round(total_free / window_h * 100) if window_h else 0
        print(f"  Availability score:  {avail_pct}% of your week is open")
        print("=" * 58 + "\n")


# ─────────────────────────────────────────────────────────────────────────────

class IncomeMode:
    """
    MODE B: Income Mode
    -------------------
    Calculates exactly how much you will earn this week from your
    scheduled shifts.  No free-time data — just the money.

    Usage:
        mode = IncomeMode()
        data = mode.run()     # get income data as a dict
        mode.display()        # print it to the terminal
    """

    def run(self) -> dict:
        """
        Returns a dict with:
            "by_job"           : income breakdown per job
            "total_hours"      : float — all work hours this week
            "total_income"     : float — total estimated earnings
            "average_hourly"   : float — weighted average rate

        Example:
            {
                "by_job": {
                    "Admissions": {
                        "shifts":       [...],
                        "total_hours":  10.0,
                        "hourly_rate":  12.50,
                        "income":       125.00,
                    },
                    "Library": { ... }
                },
                "total_hours":    18.0,
                "total_income":   208.00,
                "average_hourly": 11.56,
            }
        """
        schedule = get_weekly_schedule()
        by_job:  dict[str, dict] = {}

        for day_shifts in schedule.values():
            for shift in day_shifts:
                name = shift["job_name"]
                if name not in by_job:
                    by_job[name] = {
                        "shifts":      [],
                        "total_hours": 0.0,
                        "hourly_rate": shift["hourly_rate"],
                        "income":      0.0,
                    }
                by_job[name]["shifts"].append(shift)
                by_job[name]["total_hours"] += shift["hours"]
                by_job[name]["income"]      += shift["hours"] * shift["hourly_rate"]

        # Round the per-job totals
        for job_data in by_job.values():
            job_data["total_hours"] = round(job_data["total_hours"], 2)
            job_data["income"]      = round(job_data["income"],      2)

        total_hours  = round(sum(j["total_hours"] for j in by_job.values()), 2)
        total_income = round(sum(j["income"]      for j in by_job.values()), 2)
        average_rate = round(total_income / total_hours, 2) if total_hours else 0.0

        return {
            "by_job":         by_job,
            "total_hours":    total_hours,
            "total_income":   total_income,
            "average_hourly": average_rate,
        }

    def display(self) -> None:
        """Print a formatted income summary to the terminal."""
        data = self.run()

        print("\n" + "=" * 58)
        print("  INCOME MODE  —  This Week's Earnings")
        print("=" * 58)

        if not data["by_job"]:
            print("\n  No shifts scheduled yet.\n")
            return

        for job_name, info in sorted(data["by_job"].items()):
            print(f"\n  {job_name}  (${info['hourly_rate']:.2f}/hr)")
            print(f"  {'─' * 50}")
            for s in info["shifts"]:
                start = _format_time_12h(s["start_time"])
                end   = _format_time_12h(s["end_time"])
                earn  = round(s["hours"] * info["hourly_rate"], 2)
                print(f"    {s['day']:12s}  {start} – {end}"
                      f"  ({_format_hours(s['hours'])})  →  ${earn:.2f}")
            print(f"    ── Subtotal:  {_format_hours(info['total_hours'])}"
                  f"  =  ${info['income']:.2f}")

        print(f"\n{'=' * 58}")
        print(f"  TOTAL HOURS:   {_format_hours(data['total_hours'])}")
        print(f"  TOTAL INCOME:  ${data['total_income']:.2f}")
        print(f"  AVG RATE:      ${data['average_hourly']:.2f}/hr")
        print("=" * 58 + "\n")


# ─────────────────────────────────────────────────────────────────────────────

class OpportunityMode:
    """
    MODE C: Opportunity Mode
    ------------------------
    For each free block in your week, calculates how much you COULD earn
    if you picked up extra hours at any of your existing jobs.

    This is the 'what-if I worked more?' analysis.

    Usage:
        mode = OpportunityMode()
        data = mode.run()     # get opportunity data as a dict
        mode.display()        # print it to the terminal
    """

    def run(self) -> dict:
        """
        Returns a dict keyed by day.  Each day has a list of free blocks,
        and each free block shows potential earnings per job.

        Example:
            {
                "Monday": [
                    {
                        "start":  "12:00",
                        "end":    "13:00",
                        "hours":  1.0,
                        "potential": [
                            {"job": "International Office",
                             "rate": 15.00,
                             "potential_income": 15.00},
                            {"job": "Admissions",
                             "rate": 12.50,
                             "potential_income": 12.50},
                            {"job": "Library",
                             "rate": 11.00,
                             "potential_income": 11.00},
                        ],
                        "best_job":    "International Office",
                        "best_income": 15.00,
                    },
                    ...
                ],
                ...
            }
        """
        schedule  = get_weekly_schedule()
        jobs      = get_jobs()     # all job profiles with hourly rates
        result    = {}

        for day in DAY_ORDER:
            shifts      = schedule[day]
            free_blocks = _get_free_blocks(shifts)
            day_results = []

            for block in free_blocks:
                # Calculate what each job could pay for this block's hours
                potential = sorted(
                    [
                        {
                            "job":              job["job_name"],
                            "rate":             job["hourly_rate"],
                            "potential_income": round(block["hours"] * job["hourly_rate"], 2),
                        }
                        for job in jobs
                        if job["hourly_rate"] > 0
                    ],
                    key=lambda x: x["potential_income"],
                    reverse=True,   # highest earning first
                )

                best = potential[0] if potential else None
                day_results.append({
                    "start":       block["start"],
                    "end":         block["end"],
                    "hours":       block["hours"],
                    "potential":   potential,
                    "best_job":    best["job"]            if best else None,
                    "best_income": best["potential_income"] if best else 0.0,
                })

            result[day] = day_results

        return result

    def display(self) -> None:
        """Print a formatted opportunity summary to the terminal."""
        data = self.run()
        jobs = get_jobs()

        if not jobs:
            print("\n  No job profiles found. Add jobs with add_job() first.\n")
            return

        print("\n" + "=" * 58)
        print("  OPPORTUNITY MODE  —  Your Earning Potential")
        print("=" * 58)
        print(f"\n  Rates on file:")
        for job in jobs:
            print(f"    {job['job_name']:25s}  ${job['hourly_rate']:.2f}/hr")

        total_opportunity = 0.0
        any_free = False

        for day in DAY_ORDER:
            blocks = data[day]
            if not blocks:
                continue
            any_free = True

            print(f"\n  {day}")
            print(f"  {'─' * 50}")

            for block in blocks:
                start = _format_time_12h(block["start"])
                end   = _format_time_12h(block["end"])
                print(f"\n    FREE:  {start} – {end}"
                      f"  ({_format_hours(block['hours'])})")

                if not block["potential"]:
                    print("    No job rates on file to calculate potential.")
                    continue

                for opt in block["potential"]:
                    marker = "  ★ BEST" if opt == block["potential"][0] else ""
                    print(f"      {opt['job']:25s}"
                          f"  ${opt['rate']:.2f}/hr"
                          f"  →  ${opt['potential_income']:.2f}{marker}")

                total_opportunity += block["best_income"]

        if not any_free:
            print("\n  No free blocks found — your week is fully scheduled!\n")
            return

        print(f"\n{'=' * 58}")
        print(f"  MAX POSSIBLE EARNINGS from free time:  ${total_opportunity:.2f}")
        print("  (if you filled every free block at the highest available rate)")
        print("=" * 58 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 — QUICK DEMO
# Run this file directly to see the engine in action with sample data.
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\nInitializing shift engine...\n")
    init_shift_tables()

    # ── Set up job profiles ───────────────────────────────────────────────
    print("Adding job profiles...")
    add_job("Admissions",          hourly_rate=12.50)
    add_job("Library",             hourly_rate=11.00)
    add_job("International Office", hourly_rate=15.00)

    # ── Enter this week's shifts ──────────────────────────────────────────
    print("Adding this week's shifts...")
    clear_week()   # start fresh

    # Admissions
    add_shift("Admissions", "Monday",    "09:00", "12:00")
    add_shift("Admissions", "Wednesday", "14:00", "17:00")
    add_shift("Admissions", "Friday",    "10:00", "13:00")

    # Library
    add_shift("Library",   "Tuesday",   "13:00", "16:00")

    # International Office
    add_shift("International Office", "Thursday", "10:00", "14:00")

    # ── Run each mode SEPARATELY ──────────────────────────────────────────
    print("\nRunning Mode A — Free Time...")
    FreeTimeMode().display()

    print("Running Mode B — Income...")
    IncomeMode().display()

    print("Running Mode C — Opportunity...")
    OpportunityMode().display()
