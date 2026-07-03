"""
db_pg.py — PostgreSQL-compatible versions of core database operations.

Called by database.py when DATABASE_URL is set (production/cloud).
Uses %s placeholders and PostgreSQL-specific upsert syntax.

Never import this directly — always go through database.py which
routes to the right backend via db_connection.get_connection().
"""
from __future__ import annotations

from model import Job, Expense


def _execute(conn, sql: str, params: tuple = ()):
    """Run a query against a psycopg2 connection and return the cursor.

    psycopg2 connections don't have a `.execute()` convenience method the
    way sqlite3 connections do — you have to open a cursor first. This
    wrapper exists so every call site below can keep the same
    `_execute(conn, sql, params).fetchone()/.fetchall()` shape that
    database.py's SQLite path already uses via _execute(conn, ...).
    """
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur


# ── Schema ────────────────────────────────────────────────────────────────────

INIT_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id        SERIAL PRIMARY KEY,
    name      TEXT NOT NULL,
    amount    REAL,
    frequency TEXT DEFAULT 'Weekly',
    user_id   INTEGER DEFAULT 1,
    UNIQUE(name, user_id)
);

CREATE TABLE IF NOT EXISTS expenses (
    id        SERIAL PRIMARY KEY,
    name      TEXT NOT NULL,
    amount    REAL,
    category  TEXT,
    date      TEXT,
    frequency TEXT DEFAULT 'Monthly',
    user_id   INTEGER DEFAULT 1,
    UNIQUE(name, user_id)
);

CREATE TABLE IF NOT EXISTS settings (
    user_id INTEGER NOT NULL DEFAULT 1,
    key     TEXT    NOT NULL,
    value   REAL,
    PRIMARY KEY (user_id, key)
);

CREATE TABLE IF NOT EXISTS history (
    id              SERIAL PRIMARY KEY,
    date            TEXT UNIQUE,
    balance         REAL,
    income_weekly   REAL,
    expenses_weekly REAL,
    net_weekly      REAL,
    user_id         INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS events (
    id          SERIAL PRIMARY KEY,
    title       TEXT    NOT NULL,
    category    TEXT    NOT NULL DEFAULT 'Other',
    day         TEXT    NOT NULL,
    start_time  TEXT    NOT NULL,
    end_time    TEXT    NOT NULL,
    hourly_rate REAL    NOT NULL DEFAULT 0.0,
    notes       TEXT    NOT NULL DEFAULT '',
    shift_date  TEXT    NOT NULL DEFAULT '',
    user_id     INTEGER NOT NULL DEFAULT 1
);

INSERT INTO settings (user_id, key, value) VALUES (1, 'balance', 0) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    email           TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
"""


def init_db(conn) -> None:
    """Create all tables in PostgreSQL if they don't exist."""
    _execute(conn, INIT_SQL)


# ── Balance ───────────────────────────────────────────────────────────────────

def load_balance(conn, user_id: int = 1) -> float:
    row = _execute(conn,
        "SELECT value FROM settings WHERE key = 'balance' AND user_id = %s",
        (user_id,)
    ).fetchone()
    return row[0] if row else 0.0


def save_balance(conn, balance: float, user_id: int = 1) -> None:
    _execute(conn,
        "INSERT INTO settings (user_id, key, value) VALUES (%s, 'balance', %s) "
        "ON CONFLICT (user_id, key) DO UPDATE SET value = EXCLUDED.value",
        (user_id, balance)
    )


def load_setting(conn, key: str, default: float, user_id: int = 1) -> float:
    row = _execute(conn,
        "SELECT value FROM settings WHERE key = %s AND user_id = %s",
        (key, user_id)
    ).fetchone()
    return row[0] if row else default


def save_setting(conn, key: str, value: float, user_id: int = 1) -> None:
    _execute(conn,
        "INSERT INTO settings (user_id, key, value) VALUES (%s, %s, %s) "
        "ON CONFLICT (user_id, key) DO UPDATE SET value = EXCLUDED.value",
        (user_id, key, value)
    )


# ── Jobs ──────────────────────────────────────────────────────────────────────

def load_jobs(conn, user_id: int = 1) -> list[Job]:
    rows = _execute(conn,
        "SELECT name, amount, frequency FROM jobs WHERE user_id = %s",
        (user_id,)
    ).fetchall()
    return [Job(name, amount, frequency) for name, amount, frequency in rows]


def insert_job(conn, job: Job, user_id: int = 1) -> None:
    _execute(conn,
        "INSERT INTO jobs (name, amount, frequency, user_id) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (name, user_id) DO NOTHING",
        (job.name, job.amount, job.frequency, user_id)
    )


def remove_job(conn, name: str, user_id: int = 1) -> None:
    _execute(conn,
        "DELETE FROM jobs WHERE name = %s AND user_id = %s",
        (name, user_id)
    )


def update_job_amount(conn, name: str, amount: float, user_id: int = 1) -> None:
    _execute(conn,
        "UPDATE jobs SET amount = %s WHERE name = %s AND user_id = %s",
        (amount, name, user_id)
    )


# ── Expenses ──────────────────────────────────────────────────────────────────

def load_expenses(conn, user_id: int = 1) -> list[Expense]:
    rows = _execute(conn,
        "SELECT name, amount, category, date, frequency FROM expenses WHERE user_id = %s",
        (user_id,)
    ).fetchall()
    return [Expense(name, amount, category, date, frequency)
            for name, amount, category, date, frequency in rows]


def insert_expense(conn, expense: Expense, user_id: int = 1) -> None:
    _execute(conn,
        "INSERT INTO expenses (name, amount, category, date, frequency, user_id) "
        "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (name, user_id) DO NOTHING",
        (expense.name, expense.amount, expense.category,
         expense.date, expense.frequency, user_id)
    )


def remove_expense(conn, name: str, user_id: int = 1) -> None:
    _execute(conn,
        "DELETE FROM expenses WHERE name = %s AND user_id = %s",
        (name, user_id)
    )


# ── History ───────────────────────────────────────────────────────────────────

def record_snapshot(conn, balance: float, income: float,
                    expenses: float, net: float,
                    user_id: int = 1) -> None:
    import datetime
    today = datetime.date.today().isoformat()
    _execute(conn,
        "INSERT INTO history (date, balance, income_weekly, expenses_weekly, net_weekly, user_id) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (date) DO UPDATE SET "
        "balance = EXCLUDED.balance, "
        "income_weekly = EXCLUDED.income_weekly, "
        "expenses_weekly = EXCLUDED.expenses_weekly, "
        "net_weekly = EXCLUDED.net_weekly, "
        "user_id = EXCLUDED.user_id",
        (today, balance, income, expenses, net, user_id)
    )


def load_history(conn, user_id: int = 1) -> list[dict]:
    rows = _execute(conn,
        "SELECT date, balance, income_weekly, expenses_weekly, net_weekly "
        "FROM history WHERE user_id = %s ORDER BY date ASC",
        (user_id,)
    ).fetchall()
    return [
        {"date": r[0], "balance": r[1], "income": r[2],
         "expenses": r[3], "net": r[4]}
        for r in rows
    ]


# ── Users ─────────────────────────────────────────────────────────────────────

def insert_user(conn, email: str, hashed_password: str) -> int:
    """Insert a new user and return their new id.

    Raises psycopg2.IntegrityError if the email already exists.
    The hashed_password must already be a bcrypt hash.
    """
    import datetime
    created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur = _execute(conn,
        "INSERT INTO users (email, hashed_password, created_at) "
        "VALUES (%s, %s, %s) RETURNING id",
        (email.lower().strip(), hashed_password, created_at),
    )
    row = cur.fetchone()
    return row[0]


def get_user_by_email(conn, email: str) -> dict | None:
    """Look up a user by email. Returns dict or None."""
    row = _execute(conn,
        "SELECT id, email, hashed_password, created_at FROM users WHERE email = %s",
        (email.lower().strip(),),
    ).fetchone()
    if row is None:
        return None
    return {"id": row[0], "email": row[1], "hashed_password": row[2], "created_at": row[3]}


def get_user_by_id(conn, user_id: int) -> dict | None:
    """Look up a user by id. Returns dict (no hashed_password) or None."""
    row = _execute(conn,
        "SELECT id, email, created_at FROM users WHERE id = %s",
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    return {"id": row[0], "email": row[1], "created_at": row[2]}


# ── Schedule / Events (shifts) ────────────────────────────────────────────────
# PostgreSQL-compatible mirrors of the events functions in database.py.
# The events table itself is created by INIT_SQL above (init_db()).

def add_event(conn, event, user_id: int = 1) -> int:
    """Insert a ScheduleEvent and return its new id."""
    shift_date = getattr(event, "shift_date", "") or ""
    cur = _execute(
        conn,
        """INSERT INTO events
               (title, category, day, start_time, end_time,
                hourly_rate, notes, shift_date, user_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING id""",
        (event.title, event.category, event.day,
         event.start_time, event.end_time,
         event.hourly_rate, event.notes, shift_date, user_id),
    )
    return cur.fetchone()[0]


def get_events(conn, day: str | None = None, user_id: int = 1) -> list:
    """Load events, optionally filtered to a single day, scoped to user_id."""
    from schedule_event import ScheduleEvent
    if day:
        rows = _execute(
            conn,
            "SELECT id, title, category, day, start_time, end_time, "
            "hourly_rate, notes, shift_date "
            "FROM events WHERE day = %s AND user_id = %s ORDER BY start_time",
            (day, user_id),
        ).fetchall()
    else:
        rows = _execute(
            conn,
            "SELECT id, title, category, day, start_time, end_time, "
            "hourly_rate, notes, shift_date "
            "FROM events WHERE user_id = %s ORDER BY day, start_time",
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


def get_events_for_week(conn, week_start, user_id: int = 1) -> list:
    """Return events whose shift_date falls within the 7-day week starting on week_start."""
    import datetime
    from schedule_event import ScheduleEvent

    if isinstance(week_start, str):
        week_start = datetime.date.fromisoformat(week_start)
    week_end = week_start + datetime.timedelta(days=6)
    start_s  = week_start.isoformat()
    end_s    = week_end.isoformat()

    rows = _execute(
        conn,
        "SELECT id, title, category, day, start_time, end_time, "
        "hourly_rate, notes, shift_date "
        "FROM events "
        "WHERE shift_date >= %s AND shift_date <= %s AND user_id = %s "
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


def update_event(conn, event_id: int, **fields) -> None:
    """Update one or more fields of an existing event."""
    allowed = {"title", "category", "day", "start_time", "end_time",
               "hourly_rate", "notes", "shift_date"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    cols = ", ".join(f"{k} = %s" for k in updates)
    vals = list(updates.values()) + [event_id]
    _execute(conn, f"UPDATE events SET {cols} WHERE id = %s", vals)


def get_events_for_date(conn, date_str: str, user_id: int = 1) -> list:
    """Return all events whose shift_date matches date_str exactly."""
    from schedule_event import ScheduleEvent
    rows = _execute(
        conn,
        "SELECT id, title, category, day, start_time, end_time, "
        "hourly_rate, notes, shift_date "
        "FROM events WHERE shift_date = %s AND user_id = %s ORDER BY start_time",
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


def get_events_for_date_range(conn, start_str: str, end_str: str, user_id: int = 1) -> list:
    """Return all events whose shift_date falls within [start_str, end_str]."""
    from schedule_event import ScheduleEvent
    rows = _execute(
        conn,
        "SELECT id, title, category, day, start_time, end_time, "
        "hourly_rate, notes, shift_date "
        "FROM events "
        "WHERE shift_date != '' AND shift_date >= %s AND shift_date <= %s "
        "AND user_id = %s "
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


def get_events_for_month(conn, year: int, month: int, user_id: int = 1) -> list:
    """Return all events for the given calendar month."""
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    start = f"{year:04d}-{month:02d}-01"
    end   = f"{year:04d}-{month:02d}-{last_day:02d}"
    return get_events_for_date_range(conn, start, end, user_id=user_id)


def delete_event_by_id(conn, event_id: int) -> None:
    """Delete an event by its primary key."""
    _execute(conn, "DELETE FROM events WHERE id = %s", (event_id,))


def get_event_by_id(conn, event_id: int, user_id: int | None = None):
    """Return a ScheduleEvent by primary key, or None if not found."""
    from schedule_event import ScheduleEvent
    if user_id is not None:
        row = _execute(
            conn,
            "SELECT id, title, category, day, start_time, end_time, "
            "hourly_rate, notes, shift_date "
            "FROM events WHERE id = %s AND user_id = %s",
            (event_id, user_id),
        ).fetchone()
    else:
        row = _execute(
            conn,
            "SELECT id, title, category, day, start_time, end_time, "
            "hourly_rate, notes, shift_date "
            "FROM events WHERE id = %s",
            (event_id,),
        ).fetchone()
    if row is None:
        return None
    return ScheduleEvent(
        title=row[1], category=row[2], day=row[3],
        start_time=row[4], end_time=row[5],
        hourly_rate=row[6], notes=row[7], id=row[0],
        shift_date=row[8] if len(row) > 8 else "",
    )
