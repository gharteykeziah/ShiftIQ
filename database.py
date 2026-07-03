"""
database.py — Database persistence for ShiftIQ.

Uses db_connection.get_connection() for all queries — works with
SQLite locally and PostgreSQL in production. Switch by setting the
DATABASE_URL environment variable (see .env.example).

All reads and writes go through this module. No other module issues raw SQL.
Uses context managers throughout so connections are always closed safely.

Tables
------
jobs        : income sources (name, amount, frequency)
expenses    : recurring costs (name, amount, category, date, frequency)
settings    : key/value store — currently holds 'balance'
history     : daily financial snapshots for trend tracking
events      : scheduled time blocks (shifts, classes, personal time)

On first run, init_db() creates all tables and migrates any legacy schema.
dedup_jobs() and dedup_expenses() are called at startup to merge near-duplicate
entries created by variant spellings (e.g. 'admissions' / 'Admissions').
"""
from __future__ import annotations


import sqlite3   # kept for init_db migration (PRAGMA is SQLite-only)
import os
from model import Job, Expense
import db_connection
from db_connection import get_connection
from utils import canon_name


def init_db() -> None:
    """Create tables if they don't exist. Migrates old schema automatically."""
    with get_connection() as conn:
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT NOT NULL,
                amount    REAL,
                frequency TEXT DEFAULT 'Weekly',
                user_id   INTEGER DEFAULT 1,
                UNIQUE(name, user_id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT NOT NULL,
                amount    REAL,
                category  TEXT,
                date      TEXT,
                frequency TEXT DEFAULT 'Monthly',
                user_id   INTEGER DEFAULT 1,
                UNIQUE(name, user_id)
            )
        """)

        # settings uses a composite primary key (user_id, key) so each user
        # has their own independent balance and other settings.
        # Detect old single-column schema and migrate transparently.
        settings_cols = [r[1] for r in c.execute("PRAGMA table_info(settings)").fetchall()]
        if "user_id" not in settings_cols and settings_cols:
            # Old schema exists — recreate with composite PK, preserving data
            c.execute("""
                CREATE TABLE settings_new (
                    user_id INTEGER NOT NULL DEFAULT 1,
                    key     TEXT    NOT NULL,
                    value   REAL,
                    PRIMARY KEY (user_id, key)
                )
            """)
            c.execute("INSERT INTO settings_new (user_id, key, value) SELECT 1, key, value FROM settings")
            c.execute("DROP TABLE settings")
            c.execute("ALTER TABLE settings_new RENAME TO settings")
        elif not settings_cols:
            c.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    user_id INTEGER NOT NULL DEFAULT 1,
                    key     TEXT    NOT NULL,
                    value   REAL,
                    PRIMARY KEY (user_id, key)
                )
            """)

        # Migrate: add user_id to jobs if not present
        cols = [r[1] for r in c.execute("PRAGMA table_info(jobs)").fetchall()]
        if "user_id" not in cols and cols:
            c.execute("ALTER TABLE jobs ADD COLUMN user_id INTEGER DEFAULT 1")
            c.execute("UPDATE jobs SET user_id = 1 WHERE user_id IS NULL")

        # Migrate: change UNIQUE(name) → UNIQUE(name, user_id) for multi-user isolation.
        # Old schema had a single-column unique on name, which silently blocks two users
        # from having the same job name. Detect by checking existing indexes.
        job_indexes = c.execute("PRAGMA index_list(jobs)").fetchall()
        has_composite_jobs = any(
            {"name", "user_id"} == {r[2] for r in c.execute(f"PRAGMA index_info('{idx[1]}')").fetchall()}
            for idx in job_indexes
        )
        if not has_composite_jobs and c.execute("PRAGMA table_info(jobs)").fetchall():
            c.execute("""
                CREATE TABLE jobs_migrated (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    name      TEXT NOT NULL,
                    amount    REAL,
                    frequency TEXT DEFAULT 'Weekly',
                    user_id   INTEGER DEFAULT 1,
                    UNIQUE(name, user_id)
                )
            """)
            c.execute("INSERT OR IGNORE INTO jobs_migrated (id, name, amount, frequency, user_id) "
                      "SELECT id, name, amount, frequency, user_id FROM jobs")
            c.execute("DROP TABLE jobs")
            c.execute("ALTER TABLE jobs_migrated RENAME TO jobs")

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

        # Migrate: add user_id to expenses if not present
        cols = [r[1] for r in c.execute("PRAGMA table_info(expenses)").fetchall()]
        if "user_id" not in cols and cols:
            c.execute("ALTER TABLE expenses ADD COLUMN user_id INTEGER DEFAULT 1")
            c.execute("UPDATE expenses SET user_id = 1 WHERE user_id IS NULL")

        # Migrate old expenses table (no frequency column)
        cols = [r[1] for r in c.execute("PRAGMA table_info(expenses)").fetchall()]
        if "frequency" not in cols:
            c.execute("ALTER TABLE expenses ADD COLUMN frequency TEXT DEFAULT 'Monthly'")

        # Migrate: change UNIQUE(name) → UNIQUE(name, user_id) for multi-user isolation.
        exp_indexes = c.execute("PRAGMA index_list(expenses)").fetchall()
        has_composite_expenses = any(
            {"name", "user_id"} == {r[2] for r in c.execute(f"PRAGMA index_info('{idx[1]}')").fetchall()}
            for idx in exp_indexes
        )
        if not has_composite_expenses and c.execute("PRAGMA table_info(expenses)").fetchall():
            c.execute("""
                CREATE TABLE expenses_migrated (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    name      TEXT NOT NULL,
                    amount    REAL,
                    category  TEXT,
                    date      TEXT,
                    frequency TEXT DEFAULT 'Monthly',
                    user_id   INTEGER DEFAULT 1,
                    UNIQUE(name, user_id)
                )
            """)
            c.execute("INSERT OR IGNORE INTO expenses_migrated (id, name, amount, category, date, frequency, user_id) "
                      "SELECT id, name, amount, category, date, frequency, user_id FROM expenses")
            c.execute("DROP TABLE expenses")
            c.execute("ALTER TABLE expenses_migrated RENAME TO expenses")

        # History table for trend tracking
        # date remains UNIQUE so ON CONFLICT(date) in record_snapshot() works.
        # Per-user date uniqueness is a Phase 3 migration.
        c.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                date            TEXT UNIQUE,
                balance         REAL,
                income_weekly   REAL,
                expenses_weekly REAL,
                net_weekly      REAL,
                user_id         INTEGER DEFAULT 1
            )
        """)

        # Migrate: add user_id to history if not present
        hist_cols = [r[1] for r in c.execute("PRAGMA table_info(history)").fetchall()]
        if "user_id" not in hist_cols and hist_cols:
            c.execute("ALTER TABLE history ADD COLUMN user_id INTEGER DEFAULT 1")
            c.execute("UPDATE history SET user_id = 1 WHERE user_id IS NULL")

        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                email           TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                created_at      TEXT NOT NULL
            )
        """)

        c.execute("INSERT OR IGNORE INTO settings (user_id, key, value) VALUES (1, 'balance', 0)")
        conn.commit()


# ── Users ─────────────────────────────────────────────────────────────────────

def insert_user(email: str, hashed_password: str) -> int:
    """Insert a new user and return their new id.

    Raises sqlite3.IntegrityError if the email already exists.
    The caller (register endpoint) catches this and returns HTTP 409.
    The hashed_password must already be a bcrypt hash — never pass plain text.
    """
    import datetime
    created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO users (email, hashed_password, created_at) VALUES (?, ?, ?)",
            (email.lower().strip(), hashed_password, created_at),
        )
        conn.commit()
        return cur.lastrowid


def get_user_by_email(email: str) -> dict | None:
    """Look up a user by email address.

    Returns a dict with keys: id, email, hashed_password, created_at.
    Returns None if no user with that email exists.
    Email lookup is case-insensitive (stored lowercase).
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, email, hashed_password, created_at FROM users WHERE email = ?",
            (email.lower().strip(),),
        ).fetchone()
    if row is None:
        return None
    return {"id": row[0], "email": row[1], "hashed_password": row[2], "created_at": row[3]}


def get_user_by_id(user_id: int) -> dict | None:
    """Look up a user by their primary key id.

    Returns a dict with keys: id, email, created_at (no hashed_password).
    Returns None if no user with that id exists.
    Used by get_current_user() to verify the token subject still exists.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return {"id": row[0], "email": row[1], "created_at": row[2]}


def load_balance(user_id: int = 1) -> float:
    """Load the saved balance from settings for a specific user."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = 'balance' AND user_id = ?",
            (user_id,)
        ).fetchone()
    return row[0] if row else 0.0


def save_balance(balance: float, user_id: int = 1) -> None:
    """Persist the current balance for a specific user."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (user_id, key, value) VALUES (?, 'balance', ?)",
            (user_id, balance)
        )
        conn.commit()


def load_setting(key: str, default: float, user_id: int = 1) -> float:
    """Load a named setting for a user. Returns default if not found."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ? AND user_id = ?",
            (key, user_id)
        ).fetchone()
    return row[0] if row else default


def save_setting(key: str, value: float, user_id: int = 1) -> None:
    """Persist a named setting for a user."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (user_id, key, value) VALUES (?, ?, ?)",
            (user_id, key, value)
        )
        conn.commit()


def load_jobs(user_id: int = 1) -> list[Job]:
    """Load all jobs for a specific user."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT name, amount, frequency FROM jobs WHERE user_id = ?",
            (user_id,)
        ).fetchall()
    return [Job(name, amount, frequency) for name, amount, frequency in rows]


def insert_job(job: Job, user_id: int = 1) -> None:
    """Insert a new job for a user. Ignores duplicates (name is UNIQUE)."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO jobs (name, amount, frequency, user_id) VALUES (?, ?, ?, ?)",
            (job.name, job.amount, job.frequency, user_id)
        )
        conn.commit()


def remove_job(name: str, user_id: int = 1) -> None:
    """Delete a job by name for a specific user."""
    with get_connection() as conn:
        conn.execute("DELETE FROM jobs WHERE name = ? AND user_id = ?", (name, user_id))
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
    Canonical-deduplicate jobs table on startup, scoped per user.
    'admissions', 'Admissions', 'admission' → one 'Admissions' entry.
    Keeps the row with the highest amount. Never touches another user's rows.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, amount, user_id FROM jobs ORDER BY amount DESC"
        ).fetchall()
        seen: dict[tuple, int] = {}   # (user_id, canon_key) → id to keep
        to_delete: list[int] = []
        for row_id, name, _, user_id in rows:
            key = (user_id, _canon_db(name))
            if key in seen:
                to_delete.append(row_id)
            else:
                seen[key] = row_id
                # Rename to canonical form
                conn.execute(
                    "UPDATE jobs SET name = ? WHERE id = ?", (_canon_db(name), row_id)
                )
        for del_id in to_delete:
            conn.execute("DELETE FROM jobs WHERE id = ?", (del_id,))
        conn.commit()


def dedup_expenses() -> None:
    """
    Canonical-deduplicate expenses table on startup, scoped per user.
    'rent', 'Rent', 'rents' → one 'Rent' entry (highest amount kept).
    Never touches another user's rows.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, amount, user_id FROM expenses ORDER BY amount DESC"
        ).fetchall()
        seen: dict[tuple, int] = {}
        to_delete: list[int] = []
        for row_id, name, _, user_id in rows:
            key = (user_id, _canon_db(name))
            if key in seen:
                to_delete.append(row_id)
            else:
                seen[key] = row_id
                conn.execute(
                    "UPDATE expenses SET name = ? WHERE id = ?", (_canon_db(name), row_id)
                )
        for del_id in to_delete:
            conn.execute("DELETE FROM expenses WHERE id = ?", (del_id,))
        conn.commit()


def update_events_rate(job_title: str, rate: float, threshold: float = 0.82,
                       user_id: int = 1) -> None:
    """
    Set hourly_rate on all Work events for a specific user whose canonical
    name matches job_title. 'admission', 'Admissions', 'admissions' all update
    together — but only for the given user (defaults to 1 for the desktop app).
    """
    target_canon = _canon_db(job_title)
    with get_connection() as conn:
        titles = conn.execute(
            "SELECT DISTINCT title FROM events WHERE category = 'Work' AND user_id = ?",
            (user_id,),
        ).fetchall()
        for (title,) in titles:
            if _canon_db(title) == target_canon:
                conn.execute(
                    "UPDATE events SET hourly_rate = ? "
                    "WHERE title = ? AND category = 'Work' AND user_id = ?",
                    (rate, title, user_id)
                )
        conn.commit()


def update_job_amount(name: str, amount: float, user_id: int = 1) -> None:
    """Update the income amount for an existing job (used by schedule sync)."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE jobs SET amount = ? WHERE name = ? AND user_id = ?",
            (amount, name, user_id)
        )
        conn.commit()


def load_expenses(user_id: int = 1) -> list[Expense]:
    """Load all expenses for a specific user."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT name, amount, category, date, frequency FROM expenses WHERE user_id = ?",
            (user_id,)
        ).fetchall()
    return [Expense(name, amount, category, date, frequency)
            for name, amount, category, date, frequency in rows]


def insert_expense(expense: Expense, user_id: int = 1) -> None:
    """Insert a new expense for a user. Ignores duplicates (name is UNIQUE)."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO expenses (name, amount, category, date, frequency, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (expense.name, expense.amount, expense.category,
             expense.date, expense.frequency, user_id)
        )
        conn.commit()


def remove_expense(name: str, user_id: int = 1) -> None:
    """Delete an expense by name for a specific user."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM expenses WHERE name = ? AND user_id = ?",
            (name, user_id)
        )
        conn.commit()


# ── History / Trend Tracking ──────────────────────────────────────────────────

def record_snapshot(
    balance: float, income: float, expenses: float, net: float,
    user_id: int = 1,
) -> None:
    """
    Save today's financial snapshot to the history table for a specific user.
    One record per day — if today already exists, it updates it.
    """
    import datetime
    today = datetime.date.today().isoformat()
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO history (date, balance, income_weekly, expenses_weekly, net_weekly, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                balance         = excluded.balance,
                income_weekly   = excluded.income_weekly,
                expenses_weekly = excluded.expenses_weekly,
                net_weekly      = excluded.net_weekly,
                user_id         = excluded.user_id
        """, (today, balance, income, expenses, net, user_id))
        conn.commit()


def load_history(user_id: int = 1) -> list[dict]:
    """Return all history snapshots for a user, ordered by date ascending."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT date, balance, income_weekly, expenses_weekly, net_weekly
            FROM history WHERE user_id = ? ORDER BY date ASC
        """, (user_id,)).fetchall()
    return [
        {"date": r[0], "balance": r[1], "income": r[2],
         "expenses": r[3], "net": r[4]}
        for r in rows
    ]


# ── Schedule / Events ────────────────────────────────────────────────────────

def init_events_table() -> None:
    """Create the events table if it does not yet exist, and migrate schema."""
    with get_connection() as conn:
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
                shift_date  TEXT    NOT NULL DEFAULT '',
                user_id     INTEGER NOT NULL DEFAULT 1
            )
        """)
        # Migrate: add shift_date if table existed without it
        cols = [r[1] for r in conn.execute("PRAGMA table_info(events)").fetchall()]
        if "shift_date" not in cols:
            conn.execute("ALTER TABLE events ADD COLUMN shift_date TEXT NOT NULL DEFAULT ''")
        # Migrate: add user_id if table existed without it
        if "user_id" not in cols:
            conn.execute("ALTER TABLE events ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
        conn.commit()


def add_event(event, user_id: int = 1) -> int:
    """
    Insert a ScheduleEvent and return its new id.
    Accepts any object with the right fields (duck-typed).
    shift_date is stored when present; defaults to '' for legacy callers.
    user_id scopes the event to a specific account (default 1 for desktop app).
    """
    shift_date = getattr(event, "shift_date", "") or ""
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO events
                   (title, category, day, start_time, end_time,
                    hourly_rate, notes, shift_date, user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event.title, event.category, event.day,
             event.start_time, event.end_time,
             event.hourly_rate, event.notes, shift_date, user_id),
        )
        conn.commit()
        return cur.lastrowid


def get_events(day: str | None = None, user_id: int = 1) -> list:
    """
    Load events from the database, scoped to the given user.
    If day is given, filter to that day only; otherwise return all.
    Returns a list of ScheduleEvent instances.
    user_id defaults to 1 so the desktop app (no auth) is unaffected.
    """
    from schedule_event import ScheduleEvent
    with get_connection() as conn:
        if day:
            rows = conn.execute(
                "SELECT id, title, category, day, start_time, end_time, "
                "hourly_rate, notes, shift_date "
                "FROM events WHERE day = ? AND user_id = ? ORDER BY start_time",
                (day, user_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, category, day, start_time, end_time, "
                "hourly_rate, notes, shift_date "
                "FROM events WHERE user_id = ? ORDER BY day, start_time",
                (user_id,),
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


def get_events_for_week(week_start, user_id: int = 1) -> list:
    """
    Return all events whose shift_date falls within the 7-day week
    starting on *week_start* (a datetime.date or ISO string), scoped to user_id.

    Events with no shift_date (legacy data) are NOT included — use
    get_events() for a full unfiltered list.
    user_id defaults to 1 so the desktop app (no auth) is unaffected.
    """
    import datetime
    from schedule_event import ScheduleEvent

    if isinstance(week_start, str):
        week_start = datetime.date.fromisoformat(week_start)
    week_end = week_start + datetime.timedelta(days=6)
    start_s  = week_start.isoformat()
    end_s    = week_end.isoformat()

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, title, category, day, start_time, end_time, "
            "hourly_rate, notes, shift_date "
            "FROM events "
            "WHERE shift_date >= ? AND shift_date <= ? AND user_id = ? "
            "ORDER BY shift_date, start_time",
            (start_s, end_s, user_id),
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
    with get_connection() as conn:
        conn.execute(f"UPDATE events SET {cols} WHERE id = ?", vals)
        conn.commit()


def get_events_for_date(date_str: str, user_id: int = 1) -> list:
    """
    Return all events whose shift_date matches *date_str* exactly, scoped to user_id.
    *date_str* must be ISO "YYYY-MM-DD".
    user_id defaults to 1 so the desktop app (no auth) is unaffected.
    """
    from schedule_event import ScheduleEvent
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, title, category, day, start_time, end_time, "
            "hourly_rate, notes, shift_date "
            "FROM events WHERE shift_date = ? AND user_id = ? ORDER BY start_time",
            (date_str, user_id),
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


def get_events_for_date_range(start_str: str, end_str: str, user_id: int = 1) -> list:
    """
    Return all events whose shift_date falls within [start_str, end_str], scoped to user_id.
    Both arguments must be ISO "YYYY-MM-DD" strings.
    Events with no shift_date (legacy data) are excluded.
    Results are sorted by shift_date, then start_time.
    user_id defaults to 1 so the desktop app (no auth) is unaffected.
    """
    from schedule_event import ScheduleEvent
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, title, category, day, start_time, end_time, "
            "hourly_rate, notes, shift_date "
            "FROM events "
            "WHERE shift_date != '' AND shift_date >= ? AND shift_date <= ? "
            "AND user_id = ? "
            "ORDER BY shift_date, start_time",
            (start_str, end_str, user_id),
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


def get_events_for_month(year: int, month: int, user_id: int = 1) -> list:
    """
    Return all events for the given calendar month, scoped to user_id.
    Delegates to get_events_for_date_range with the month's first/last day.
    user_id defaults to 1 so the desktop app (no auth) is unaffected.
    """
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    start    = f"{year:04d}-{month:02d}-01"
    end      = f"{year:04d}-{month:02d}-{last_day:02d}"
    return get_events_for_date_range(start, end, user_id=user_id)


def delete_event_by_id(event_id: int) -> None:
    """Delete an event by its primary key."""
    with get_connection() as conn:
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
    sqlite_file = db_connection.SQLITE_FILE
    folder  = os.path.dirname(sqlite_file) or '.'
    dest    = os.path.join(folder, f"backup_{today}.db")
    shutil.copy2(sqlite_file, dest)
    return dest
