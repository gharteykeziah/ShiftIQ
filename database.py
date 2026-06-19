"""
database.py — SQLite persistence for the Financial Reality Engine.

Uses context managers (with sqlite3.connect(...) as conn) throughout
so connections are always closed safely, even if an error occurs.
"""
from __future__ import annotations


import sqlite3
import os
from model import Job, Expense
from config import DB_NAME
from utils import canon_name


def init_db() -> None:
    """Create tables if they don't exist. Migrates old schema automatically."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT UNIQUE,
                amount    REAL,
                frequency TEXT DEFAULT 'Weekly'
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT UNIQUE,
                amount    REAL,
                category  TEXT,
                date      TEXT,
                frequency TEXT DEFAULT 'Monthly'
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value REAL
            )
        """)

        # Migrate old jobs table (hourly_rate + hours_per_week → amount + frequency)
        cols = [r[1] for r in c.execute("PRAGMA table_info(jobs)").fetchall()]
        if "hourly_rate" in cols:
            c.execute("ALTER TABLE jobs ADD COLUMN amount    REAL")
            c.execute("ALTER TABLE jobs ADD COLUMN frequency TEXT DEFAULT 'Weekly'")
            c.execute("UPDATE jobs SET amount = hourly_rate * hours_per_week, frequency = 'Weekly'")
            c.execute("""
                CREATE TABLE jobs_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    amount REAL,
                    frequency TEXT DEFAULT 'Weekly'
                )
            """)
            c.execute("INSERT INTO jobs_new (name, amount, frequency) SELECT name, amount, frequency FROM jobs")
            c.execute("DROP TABLE jobs")
            c.execute("ALTER TABLE jobs_new RENAME TO jobs")

        # Migrate old expenses table (no frequency column)
        cols = [r[1] for r in c.execute("PRAGMA table_info(expenses)").fetchall()]
        if "frequency" not in cols:
            c.execute("ALTER TABLE expenses ADD COLUMN frequency TEXT DEFAULT 'Monthly'")

        # History table for trend tracking
        c.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                date          TEXT UNIQUE,
                balance       REAL,
                income_weekly REAL,
                expenses_weekly REAL,
                net_weekly    REAL
            )
        """)

        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('balance', 0)")
        conn.commit()


def load_balance() -> float:
    """Load the saved balance from settings."""
    with sqlite3.connect(DB_NAME) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = 'balance'").fetchone()
    return row[0] if row else 0.0


def save_balance(balance: float) -> None:
    """Persist the current balance."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('balance', ?)",
            (balance,)
        )
        conn.commit()


def load_setting(key: str, default: float) -> float:
    """Load a named setting. Returns default if not found."""
    with sqlite3.connect(DB_NAME) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else default


def save_setting(key: str, value: float) -> None:
    """Persist a named setting."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        conn.commit()


def load_jobs() -> list[Job]:
    """Load all jobs from the database."""
    with sqlite3.connect(DB_NAME) as conn:
        rows = conn.execute("SELECT name, amount, frequency FROM jobs").fetchall()
    return [Job(name, amount, frequency) for name, amount, frequency in rows]


def insert_job(job: Job) -> None:
    """Insert a new job. Ignores duplicates (name is UNIQUE)."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO jobs (name, amount, frequency) VALUES (?, ?, ?)",
            (job.name, job.amount, job.frequency)
        )
        conn.commit()


def remove_job(name: str) -> None:
    """Delete a job by name."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM jobs WHERE name = ?", (name,))
        conn.commit()


def _fuzzy_group(rows: list[tuple], threshold: float = 0.82) -> list[list[tuple]]:
    """
    Group (id, name, amount) rows by fuzzy name similarity.
    Returns a list of clusters; each cluster is a list of rows.
    """
    from difflib import SequenceMatcher
    clusters: list[list[tuple]] = []
    for row in rows:
        placed = False
        for cluster in clusters:
            rep = cluster[0][1]   # name of first row in cluster
            ratio = SequenceMatcher(
                None, row[1].strip().lower(), rep.strip().lower()
            ).ratio()
            if ratio >= threshold:
                cluster.append(row)
                placed = True
                break
        if not placed:
            clusters.append([row])
    return clusters


def _canon_db(name: str) -> str:
    """Canonical name for DB dedup — delegates to utils.canon_name()."""
    return canon_name(name)


def dedup_jobs() -> None:
    """
    Canonical-deduplicate jobs table on startup.
    'admissions', 'Admissions', 'admission' → one 'Admissions' entry.
    Keeps the row with the highest amount.
    """
    with sqlite3.connect(DB_NAME) as conn:
        rows = conn.execute(
            "SELECT id, name, amount FROM jobs ORDER BY amount DESC"
        ).fetchall()
        seen: dict[str, int] = {}   # canon_key → id to keep
        to_delete: list[int] = []
        for row_id, name, _ in rows:
            key = _canon_db(name)
            if key in seen:
                to_delete.append(row_id)
            else:
                seen[key] = row_id
                # Rename to canonical form
                conn.execute(
                    "UPDATE jobs SET name = ? WHERE id = ?", (key, row_id)
                )
        for del_id in to_delete:
            conn.execute("DELETE FROM jobs WHERE id = ?", (del_id,))
        conn.commit()


def dedup_expenses() -> None:
    """
    Canonical-deduplicate expenses table on startup.
    'rent', 'Rent', 'rents' → one 'Rent' entry (highest amount kept).
    """
    with sqlite3.connect(DB_NAME) as conn:
        rows = conn.execute(
            "SELECT id, name, amount FROM expenses ORDER BY amount DESC"
        ).fetchall()
        seen: dict[str, int] = {}
        to_delete: list[int] = []
        for row_id, name, _ in rows:
            key = _canon_db(name)
            if key in seen:
                to_delete.append(row_id)
            else:
                seen[key] = row_id
                conn.execute(
                    "UPDATE expenses SET name = ? WHERE id = ?", (key, row_id)
                )
        for del_id in to_delete:
            conn.execute("DELETE FROM expenses WHERE id = ?", (del_id,))
        conn.commit()


def update_events_rate(job_title: str, rate: float, threshold: float = 0.82) -> None:
    """
    Set hourly_rate on ALL Work events whose canonical name matches job_title.
    'admission', 'Admissions', 'admissions' all update together.
    """
    target_canon = _canon_db(job_title)
    with sqlite3.connect(DB_NAME) as conn:
        titles = conn.execute(
            "SELECT DISTINCT title FROM events WHERE category = 'Work'"
        ).fetchall()
        for (title,) in titles:
            if _canon_db(title) == target_canon:
                conn.execute(
                    "UPDATE events SET hourly_rate = ? "
                    "WHERE title = ? AND category = 'Work'",
                    (rate, title)
                )
        conn.commit()


def update_job_amount(name: str, amount: float) -> None:
    """Update the income amount for an existing job (used by schedule sync)."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("UPDATE jobs SET amount = ? WHERE name = ?", (amount, name))
        conn.commit()


def load_expenses() -> list[Expense]:
    """Load all expenses from the database."""
    with sqlite3.connect(DB_NAME) as conn:
        rows = conn.execute(
            "SELECT name, amount, category, date, frequency FROM expenses"
        ).fetchall()
    return [Expense(name, amount, category, date, frequency)
            for name, amount, category, date, frequency in rows]


def insert_expense(expense: Expense) -> None:
    """Insert a new expense. Ignores duplicates (name is UNIQUE)."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO expenses (name, amount, category, date, frequency) VALUES (?, ?, ?, ?, ?)",
            (expense.name, expense.amount, expense.category, expense.date, expense.frequency)
        )
        conn.commit()


def remove_expense(name: str) -> None:
    """Delete an expense by name."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM expenses WHERE name = ?", (name,))
        conn.commit()


# ── History / Trend Tracking ──────────────────────────────────────────────────

def record_snapshot(balance: float, income: float, expenses: float, net: float) -> None:
    """
    Save today's financial snapshot to the history table.
    One record per day — if today already exists, it updates it.
    """
    import datetime
    today = datetime.date.today().isoformat()
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            INSERT INTO history (date, balance, income_weekly, expenses_weekly, net_weekly)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                balance         = excluded.balance,
                income_weekly   = excluded.income_weekly,
                expenses_weekly = excluded.expenses_weekly,
                net_weekly      = excluded.net_weekly
        """, (today, balance, income, expenses, net))
        conn.commit()


def load_history() -> list[dict]:
    """Return all history snapshots ordered by date ascending."""
    with sqlite3.connect(DB_NAME) as conn:
        rows = conn.execute("""
            SELECT date, balance, income_weekly, expenses_weekly, net_weekly
            FROM history ORDER BY date ASC
        """).fetchall()
    return [
        {"date": r[0], "balance": r[1], "income": r[2],
         "expenses": r[3], "net": r[4]}
        for r in rows
    ]


# ── Schedule / Events ────────────────────────────────────────────────────────

def init_events_table() -> None:
    """Create the events table if it does not yet exist, and migrate schema."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL,
                category    TEXT    NOT NULL DEFAULT 'Other',
                day         TEXT    NOT NULL,
                start_time  TEXT    NOT NULL,
                end_time    TEXT    NOT NULL,
                hourly_rate REAL    NOT NULL DEFAULT 0.0,
                notes       TEXT    NOT NULL DEFAULT '',
                shift_date  TEXT    NOT NULL DEFAULT ''
            )
        """)
        # Migrate: add shift_date if table existed without it
        cols = [r[1] for r in conn.execute("PRAGMA table_info(events)").fetchall()]
        if "shift_date" not in cols:
            conn.execute("ALTER TABLE events ADD COLUMN shift_date TEXT NOT NULL DEFAULT ''")
        conn.commit()


def add_event(event) -> int:
    """
    Insert a ScheduleEvent and return its new id.
    Accepts any object with the right fields (duck-typed).
    shift_date is stored when present; defaults to '' for legacy callers.
    """
    shift_date = getattr(event, "shift_date", "") or ""
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute(
            """INSERT INTO events
                   (title, category, day, start_time, end_time,
                    hourly_rate, notes, shift_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (event.title, event.category, event.day,
             event.start_time, event.end_time,
             event.hourly_rate, event.notes, shift_date),
        )
        conn.commit()
        return cur.lastrowid


def get_events(day: str | None = None) -> list:
    """
    Load events from the database.
    If day is given, filter to that day only; otherwise return all.
    Returns a list of ScheduleEvent instances.
    """
    from schedule_event import ScheduleEvent
    with sqlite3.connect(DB_NAME) as conn:
        if day:
            rows = conn.execute(
                "SELECT id, title, category, day, start_time, end_time, "
                "hourly_rate, notes, shift_date "
                "FROM events WHERE day = ? ORDER BY start_time",
                (day,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, category, day, start_time, end_time, "
                "hourly_rate, notes, shift_date "
                "FROM events ORDER BY day, start_time"
            ).fetchall()
    return [
        ScheduleEvent(
            title=r[1], category=r[2], day=r[3],
            start_time=r[4], end_time=r[5],
            hourly_rate=r[6], notes=r[7], id=r[0],
            shift_date=r[8] if len(r) > 8 else "",
        )
        for r in rows
    ]


def get_events_for_week(week_start) -> list:
    """
    Return all events whose shift_date falls within the 7-day week
    starting on *week_start* (a datetime.date or ISO string).

    Events with no shift_date (legacy data) are NOT included — use
    get_events() for a full unfiltered list.
    """
    import datetime
    from schedule_event import ScheduleEvent

    if isinstance(week_start, str):
        week_start = datetime.date.fromisoformat(week_start)
    week_end = week_start + datetime.timedelta(days=6)
    start_s  = week_start.isoformat()
    end_s    = week_end.isoformat()

    with sqlite3.connect(DB_NAME) as conn:
        rows = conn.execute(
            "SELECT id, title, category, day, start_time, end_time, "
            "hourly_rate, notes, shift_date "
            "FROM events "
            "WHERE shift_date >= ? AND shift_date <= ? "
            "ORDER BY shift_date, start_time",
            (start_s, end_s),
        ).fetchall()
    return [
        ScheduleEvent(
            title=r[1], category=r[2], day=r[3],
            start_time=r[4], end_time=r[5],
            hourly_rate=r[6], notes=r[7], id=r[0],
            shift_date=r[8],
        )
        for r in rows
    ]


def update_event(event_id: int, **fields) -> None:
    """
    Update one or more fields of an existing event.
    Allowed fields: title, category, day, start_time, end_time,
                    hourly_rate, notes, shift_date.
    """
    allowed = {"title", "category", "day", "start_time", "end_time",
               "hourly_rate", "notes", "shift_date"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    cols = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [event_id]
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(f"UPDATE events SET {cols} WHERE id = ?", vals)
        conn.commit()


def get_events_for_date(date_str: str) -> list:
    """
    Return all events whose shift_date matches *date_str* exactly.
    *date_str* must be ISO "YYYY-MM-DD".
    """
    from schedule_event import ScheduleEvent
    with sqlite3.connect(DB_NAME) as conn:
        rows = conn.execute(
            "SELECT id, title, category, day, start_time, end_time, "
            "hourly_rate, notes, shift_date "
            "FROM events WHERE shift_date = ? ORDER BY start_time",
            (date_str,),
        ).fetchall()
    return [
        ScheduleEvent(
            title=r[1], category=r[2], day=r[3],
            start_time=r[4], end_time=r[5],
            hourly_rate=r[6], notes=r[7], id=r[0],
            shift_date=r[8],
        )
        for r in rows
    ]


def get_events_for_date_range(start_str: str, end_str: str) -> list:
    """
    Return all events whose shift_date falls within [start_str, end_str].
    Both arguments must be ISO "YYYY-MM-DD" strings.
    Events with no shift_date (legacy data) are excluded.
    Results are sorted by shift_date, then start_time.
    """
    from schedule_event import ScheduleEvent
    with sqlite3.connect(DB_NAME) as conn:
        rows = conn.execute(
            "SELECT id, title, category, day, start_time, end_time, "
            "hourly_rate, notes, shift_date "
            "FROM events "
            "WHERE shift_date != '' AND shift_date >= ? AND shift_date <= ? "
            "ORDER BY shift_date, start_time",
            (start_str, end_str),
        ).fetchall()
    return [
        ScheduleEvent(
            title=r[1], category=r[2], day=r[3],
            start_time=r[4], end_time=r[5],
            hourly_rate=r[6], notes=r[7], id=r[0],
            shift_date=r[8],
        )
        for r in rows
    ]


def get_events_for_month(year: int, month: int) -> list:
    """
    Return all events for the given calendar month.
    Delegates to get_events_for_date_range with the month's first/last day.
    """
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    start    = f"{year:04d}-{month:02d}-01"
    end      = f"{year:04d}-{month:02d}-{last_day:02d}"
    return get_events_for_date_range(start, end)


def delete_event_by_id(event_id: int) -> None:
    """Delete an event by its primary key."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
        conn.commit()


# ── Database Backup ───────────────────────────────────────────────────────────

def backup_database() -> str:
    """
    Copy finance.db to backup_YYYY-MM-DD.db in the same folder.
    Returns the path of the backup file.
    """
    import datetime, shutil
    today   = datetime.date.today().isoformat()
    folder  = os.path.dirname(DB_NAME)
    dest    = os.path.join(folder, f"backup_{today}.db")
    shutil.copy2(DB_NAME, dest)
    return dest
