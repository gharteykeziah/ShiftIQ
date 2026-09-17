"""
db_connection.py — Single source of truth for database connections.

Returns a SQLite connection locally (DATABASE_URL is empty)
or a PostgreSQL connection in production (DATABASE_URL is set).

Usage:
    from backend.core.db_connection import get_connection

    with get_connection() as conn:
        conn.execute("SELECT ...")

Every function in database.py uses this — nothing else calls
sqlite3.connect() or psycopg2.connect() directly.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Generator

# ── Config ────────────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL", "")  # empty = use SQLite
SQLITE_FILE  = os.getenv("SQLITE_FILE", "finance.db")


def is_postgres() -> bool:
    """True when a PostgreSQL DATABASE_URL is configured."""
    return bool(DATABASE_URL and DATABASE_URL.startswith("postgresql"))


# Keep old private name as alias so existing callers don't break
_is_postgres = is_postgres


@contextmanager
def get_connection() -> Generator:
    """
    Context manager that yields an open database connection.

    - No DATABASE_URL  →  SQLite (local file, default: finance.db)
    - DATABASE_URL set →  PostgreSQL (cloud / production)

    Caller uses it exactly like sqlite3.connect():

        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM jobs").fetchall()
    """
    if _is_postgres():
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(SQLITE_FILE)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
