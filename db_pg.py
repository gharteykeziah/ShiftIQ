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
    conn.execute(INIT_SQL)


# ── Balance ───────────────────────────────────────────────────────────────────

def load_balance(conn, user_id: int = 1) -> float:
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'balance' AND user_id = %s",
        (user_id,)
    ).fetchone()
    return row[0] if row else 0.0


def save_balance(conn, balance: float, user_id: int = 1) -> None:
    conn.execute(
        "INSERT INTO settings (user_id, key, value) VALUES (%s, 'balance', %s) "
        "ON CONFLICT (user_id, key) DO UPDATE SET value = EXCLUDED.value",
        (user_id, balance)
    )


def load_setting(conn, key: str, default: float, user_id: int = 1) -> float:
    row = conn.execute(
        "SELECT value FROM settings WHERE key = %s AND user_id = %s",
        (key, user_id)
    ).fetchone()
    return row[0] if row else default


def save_setting(conn, key: str, value: float, user_id: int = 1) -> None:
    conn.execute(
        "INSERT INTO settings (user_id, key, value) VALUES (%s, %s, %s) "
        "ON CONFLICT (user_id, key) DO UPDATE SET value = EXCLUDED.value",
        (user_id, key, value)
    )


# ── Jobs ──────────────────────────────────────────────────────────────────────

def load_jobs(conn, user_id: int = 1) -> list[Job]:
    rows = conn.execute(
        "SELECT name, amount, frequency FROM jobs WHERE user_id = %s",
        (user_id,)
    ).fetchall()
    return [Job(name, amount, frequency) for name, amount, frequency in rows]


def insert_job(conn, job: Job, user_id: int = 1) -> None:
    conn.execute(
        "INSERT INTO jobs (name, amount, frequency, user_id) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (name, user_id) DO NOTHING",
        (job.name, job.amount, job.frequency, user_id)
    )


def remove_job(conn, name: str, user_id: int = 1) -> None:
    conn.execute(
        "DELETE FROM jobs WHERE name = %s AND user_id = %s",
        (name, user_id)
    )


def update_job_amount(conn, name: str, amount: float, user_id: int = 1) -> None:
    conn.execute(
        "UPDATE jobs SET amount = %s WHERE name = %s AND user_id = %s",
        (amount, name, user_id)
    )


# ── Expenses ──────────────────────────────────────────────────────────────────

def load_expenses(conn, user_id: int = 1) -> list[Expense]:
    rows = conn.execute(
        "SELECT name, amount, category, date, frequency FROM expenses WHERE user_id = %s",
        (user_id,)
    ).fetchall()
    return [Expense(name, amount, category, date, frequency)
            for name, amount, category, date, frequency in rows]


def insert_expense(conn, expense: Expense, user_id: int = 1) -> None:
    conn.execute(
        "INSERT INTO expenses (name, amount, category, date, frequency, user_id) "
        "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (name, user_id) DO NOTHING",
        (expense.name, expense.amount, expense.category,
         expense.date, expense.frequency, user_id)
    )


def remove_expense(conn, name: str, user_id: int = 1) -> None:
    conn.execute(
        "DELETE FROM expenses WHERE name = %s AND user_id = %s",
        (name, user_id)
    )


# ── History ───────────────────────────────────────────────────────────────────

def record_snapshot(conn, balance: float, income: float,
                    expenses: float, net: float,
                    user_id: int = 1) -> None:
    import datetime
    today = datetime.date.today().isoformat()
    conn.execute(
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
    rows = conn.execute(
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


def get_user_by_id(conn, user_id: int) -> dict | None:
    """Look up a user by id. Returns dict (no hashed_password) or None."""
    row = conn.execute(
        "SELECT id, email, created_at FROM users WHERE id = %s",
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    return {"id": row[0], "email": row[1], "created_at": row[2]}
