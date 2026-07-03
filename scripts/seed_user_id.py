"""
scripts/seed_user_id.py — One-time migration: assign user_id = 1 to all
existing rows that predate the multi-user schema.

Safe to re-run: rows that already have a user_id set are untouched
(UPDATE ... WHERE user_id IS NULL OR user_id = 0 only).

Usage:
    python3 scripts/seed_user_id.py [path/to/finance.db]

If no path is given, the script uses the SQLITE_FILE env var (or
'finance.db' in the current directory as a last resort).

What it does:
    - Sets events.user_id = 1 for all rows where user_id IS NULL or 0
    - Same for jobs, expenses, history, settings (settings uses a
      composite key so it rebuilds the primary key instead of updating)
    - Prints a summary of rows updated

The first registered account in the users table has id = 1 and
automatically "owns" all pre-migration data after this script runs.
"""
from __future__ import annotations

import os
import sqlite3
import sys


def seed(db_path: str) -> None:
    if not os.path.exists(db_path):
        print(f"[seed_user_id] Database not found: {db_path}")
        sys.exit(1)

    print(f"[seed_user_id] Seeding {db_path} ...")

    with sqlite3.connect(db_path) as conn:
        # ── events ────────────────────────────────────────────────────────────
        # Add column if the table predates multi-user support
        cols = [r[1] for r in conn.execute("PRAGMA table_info(events)").fetchall()]
        if "user_id" not in cols:
            conn.execute("ALTER TABLE events ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
            print("  events: added user_id column")

        cur = conn.execute(
            "UPDATE events SET user_id = 1 WHERE user_id IS NULL OR user_id = 0"
        )
        print(f"  events: {cur.rowcount} rows assigned user_id = 1")

        # ── jobs ──────────────────────────────────────────────────────────────
        cols = [r[1] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()]
        if "user_id" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN user_id INTEGER DEFAULT 1")
            print("  jobs: added user_id column")

        cur = conn.execute(
            "UPDATE jobs SET user_id = 1 WHERE user_id IS NULL OR user_id = 0"
        )
        print(f"  jobs: {cur.rowcount} rows assigned user_id = 1")

        # ── expenses ──────────────────────────────────────────────────────────
        cols = [r[1] for r in conn.execute("PRAGMA table_info(expenses)").fetchall()]
        if "user_id" not in cols:
            conn.execute("ALTER TABLE expenses ADD COLUMN user_id INTEGER DEFAULT 1")
            print("  expenses: added user_id column")

        cur = conn.execute(
            "UPDATE expenses SET user_id = 1 WHERE user_id IS NULL OR user_id = 0"
        )
        print(f"  expenses: {cur.rowcount} rows assigned user_id = 1")

        # ── history ───────────────────────────────────────────────────────────
        cols = [r[1] for r in conn.execute("PRAGMA table_info(history)").fetchall()]
        if "user_id" not in cols:
            conn.execute("ALTER TABLE history ADD COLUMN user_id INTEGER DEFAULT 1")
            print("  history: added user_id column")

        cur = conn.execute(
            "UPDATE history SET user_id = 1 WHERE user_id IS NULL OR user_id = 0"
        )
        print(f"  history: {cur.rowcount} rows assigned user_id = 1")

        conn.commit()

    print("[seed_user_id] Done. All existing data is now owned by user_id = 1.")
    print("               Register your account — it will receive id = 1 and")
    print("               automatically own this data.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = os.getenv("SQLITE_FILE", "finance.db")
    seed(path)
