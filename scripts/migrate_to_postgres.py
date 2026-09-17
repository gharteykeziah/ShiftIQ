"""
migrate_to_postgres.py — One-time migration from SQLite to PostgreSQL.

Reads all data from the local finance.db (SQLite) and writes it into
the PostgreSQL database specified by DATABASE_URL.

Run this ONCE before going live on AWS:

    1. Set DATABASE_URL in your .env or shell:
       export DATABASE_URL=postgresql://user:password@host:5432/shiftiq

    2. Run from the project root:
       python scripts/migrate_to_postgres.py

    3. Verify the output — it prints a count of every table migrated.

Safe to re-run: uses INSERT ... ON CONFLICT DO NOTHING so existing
rows are never overwritten.
"""
from __future__ import annotations

import os
import sys
import sqlite3

# ── Allow running from project root or scripts/ ───────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

import backend.core.db_pg as db_pg
from backend.core.db_connection import get_connection, is_postgres

SQLITE_FILE = os.getenv("SQLITE_FILE", "finance.db")


def _read_sqlite(query: str) -> list[tuple]:
    """Run a SELECT against the local SQLite file and return all rows."""
    if not os.path.exists(SQLITE_FILE):
        print(f"  ✗  SQLite file not found: {SQLITE_FILE}")
        sys.exit(1)
    with sqlite3.connect(SQLITE_FILE) as conn:
        return conn.execute(query).fetchall()


def migrate(pg_conn) -> None:
    """Copy every table from SQLite into the open PostgreSQL connection."""

    # ── Init schema ───────────────────────────────────────────────────────────
    print("Creating PostgreSQL schema …")
    db_pg.init_db(pg_conn)
    print("  ✓  Schema ready")

    # ── Settings (balance) ────────────────────────────────────────────────────
    rows = _read_sqlite("SELECT key, value FROM settings")
    for key, value in rows:
        pg_conn.execute(
            "INSERT INTO settings (key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO NOTHING",
            (key, value)
        )
    print(f"  ✓  settings   — {len(rows)} row(s)")

    # ── Jobs ──────────────────────────────────────────────────────────────────
    rows = _read_sqlite("SELECT name, amount, frequency FROM jobs")
    for name, amount, frequency in rows:
        pg_conn.execute(
            "INSERT INTO jobs (name, amount, frequency) VALUES (%s, %s, %s) "
            "ON CONFLICT (name) DO NOTHING",
            (name, amount, frequency)
        )
    print(f"  ✓  jobs       — {len(rows)} row(s)")

    # ── Expenses ──────────────────────────────────────────────────────────────
    rows = _read_sqlite(
        "SELECT name, amount, category, date, frequency FROM expenses"
    )
    for name, amount, category, date, frequency in rows:
        pg_conn.execute(
            "INSERT INTO expenses (name, amount, category, date, frequency) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (name) DO NOTHING",
            (name, amount, category, date, frequency)
        )
    print(f"  ✓  expenses   — {len(rows)} row(s)")

    # ── History ───────────────────────────────────────────────────────────────
    rows = _read_sqlite(
        "SELECT date, balance, income_weekly, expenses_weekly, net_weekly "
        "FROM history ORDER BY date ASC"
    )
    for date, balance, income, expenses, net in rows:
        pg_conn.execute(
            "INSERT INTO history "
            "(date, balance, income_weekly, expenses_weekly, net_weekly) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (date) DO NOTHING",
            (date, balance, income, expenses, net)
        )
    print(f"  ✓  history    — {len(rows)} row(s)")

    # ── Events ────────────────────────────────────────────────────────────────
    try:
        rows = _read_sqlite(
            "SELECT title, category, day, start_time, end_time, "
            "hourly_rate, notes, shift_date FROM events"
        )
        for title, category, day, start_time, end_time, hourly_rate, notes, shift_date in rows:
            pg_conn.execute(
                "INSERT INTO events "
                "(title, category, day, start_time, end_time, "
                "hourly_rate, notes, shift_date) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (title, category, day, start_time, end_time,
                 hourly_rate, notes, shift_date)
            )
        print(f"  ✓  events     — {len(rows)} row(s)")
    except sqlite3.OperationalError:
        print("  –  events     — table not found in SQLite, skipping")


def main() -> None:
    print("=" * 55)
    print("  ShiftIQ — SQLite → PostgreSQL Migration")
    print("=" * 55)

    if not is_postgres():
        print("\n  ERROR: DATABASE_URL is not set or is not a PostgreSQL URL.")
        print("  Set it in your .env file or shell before running this script.")
        print("  Example: DATABASE_URL=postgresql://user:pass@host:5432/shiftiq\n")
        sys.exit(1)

    print(f"\n  Source : {SQLITE_FILE}")
    print(f"  Target : {os.getenv('DATABASE_URL', '')[:40]}…\n")

    with get_connection() as pg_conn:
        migrate(pg_conn)

    print("\n  Migration complete. Verify your data at /api/state before going live.")
    print("=" * 55)


if __name__ == "__main__":
    main()
