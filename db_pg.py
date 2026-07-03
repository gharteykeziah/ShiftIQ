"""
db_pg.py — PostgreSQL-compatible versions of core database operations.

Called by database.py when DATABASE_URL is set (production/cloud).
Uses %s placeholders and PostgreSQL-specific upsert syntax.

Never import this directly — always go through database.py which
routes to the right backend via db_connection.get_connection().
"""
from __future__ import annotations

from model import Job, Expense


# ── Schema ────────────────────────────────────────────────────────────────────

INIT_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id        SERIAL PRIMARY KEY,
    name      TEXT UNIQUE,
    amount    REAL,
    frequency TEXT DEFAULT 'Weekly'
);

CREATE TABLE IF NOT EXISTS expenses (
    id        SERIAL PRIMARY KEY,
    name      TEXT UNIQUE,
    amount    REAL,
    category  TEXT,
    date      TEXT,
    frequency TEXT DEFAULT 'Monthly'
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value REAL
);

CREATE TABLE IF NOT EXISTS history (
    id              SERIAL PRIMARY KEY,
    date            TEXT UNIQUE,
    balance         REAL,
    income_weekly   REAL,
    expenses_weekly REAL,
    net_weekly      REAL
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
    shift_date  TEXT    NOT NULL DEFAULT ''
);

INSERT INTO settings (key, value) VALUES ('balance', 0) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    email           TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
"""


def init_db(conn) -> None:
    """Create all tables in PostgreSQL if they don't exist."""
    conn.execute(INIT_SQL)


# ── Balance ───────────────────────────────────────────────────────────────────

def load_balance(conn) -> float:
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'balance'"
    ).fetchone()
    return row[0] if row else 0.0


def save_balance(conn, balance: float) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES ('balance', %s) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
        (balance,)
    )


def load_setting(conn, key: str, default: float) -> float:
    row = conn.execute(
        "SELECT value FROM settings WHERE key = %s", (key,)
    ).fetchone()
    return row[0] if row else default


def save_setting(conn, key: str, value: float) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (%s, %s) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
        (key, value)
    )


# ── Jobs ──────────────────────────────────────────────────────────────────────

def load_jobs(conn) -> list[Job]:
    rows = conn.execute(
        "SELECT name, amount, frequency FROM jobs"
    ).fetchall()
    return [Job(name, amount, frequency) for name, amount, frequency in rows]


def insert_job(conn, job: Job) -> None:
    conn.execute(
        "INSERT INTO jobs (name, amount, frequency) VALUES (%s, %s, %s) "
        "ON CONFLICT (name) DO NOTHING",
        (job.name, job.amount, job.frequency)
    )


def remove_job(conn, name: str) -> None:
    conn.execute("DELETE FROM jobs WHERE name = %s", (name,))


def update_job_amount(conn, name: str, amount: float) -> None:
    conn.execute(
        "UPDATE jobs SET amount = %s WHERE name = %s", (amount, name)
    )


# ── Expenses ──────────────────────────────────────────────────────────────────

def load_expenses(conn) -> list[Expense]:
    rows = conn.execute(
        "SELECT name, amount, category, date, frequency FROM expenses"
    ).fetchall()
    return [Expense(name, amount, category, date, frequency)
            for name, amount, category, date, frequency in rows]


def insert_expense(conn, expense: Expense) -> None:
    conn.execute(
        "INSERT INTO expenses (name, amount, category, date, frequency) "
        "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (name) DO NOTHING",
        (expense.name, expense.amount, expense.category,
         expense.date, expense.frequency)
    )


def remove_expense(conn, name: str) -> None:
    conn.execute("DELETE FROM expenses WHERE name = %s", (name,))


# ── History ───────────────────────────────────────────────────────────────────

def record_snapshot(conn, balance: float, income: float,
                    expenses: float, net: float) -> None:
    import datetime
    today = datetime.date.today().isoformat()
    conn.execute(
        "INSERT INTO history (date, balance, income_weekly, expenses_weekly, net_weekly) "
        "VALUES (%s, %s, %s, %s, %s) "
        "ON CONFLICT (date) DO UPDATE SET "
        "balance = EXCLUDED.balance, "
        "income_weekly = EXCLUDED.income_weekly, "
        "expenses_weekly = EXCLUDED.expenses_weekly, "
        "net_weekly = EXCLUDED.net_weekly",
        (today, balance, income, expenses, net)
    )


def load_history(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT date, balance, income_weekly, expenses_weekly, net_weekly "
        "FROM history ORDER BY date ASC"
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
    cur = conn.execute(
        "INSERT INTO users (email, hashed_password, created_at) "
        "VALUES (%s, %s, %s) RETURNING id",
        (email.lower().strip(), hashed_password, created_at),
    )
    row = cur.fetchone()
    return row[0]


def get_user_by_email(conn, email: str) -> dict | None:
    """Look up a user by email. Returns dict or None."""
    row = conn.execute(
        "SELECT id, email, hashed_password, created_at FROM users WHERE email = %s",
        (email.lower().strip(),),
    ).fetchone()
    if row is None:
        return None
    return {"id": row[0], "email": row[1], "hashed_password": row[2], "created_at": row[3]}
