"""
activity_log.py — Records every user action to activity.log.
Keeps the last 200 entries. Used by the Activity Log tab in the GUI.
"""

import datetime
import os
from backend.core.config import ACTIVITY_FILE

MAX_LINES = 200


def log(action: str) -> None:
    """Append a timestamped action entry to the activity log."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M")
    entry     = f"[{timestamp}]   {action}\n"
    try:
        with open(ACTIVITY_FILE, "a", encoding="utf-8") as f:
            f.write(entry)
        _trim()
    except OSError:
        pass   # never crash the app over logging


def recent(n: int = 50) -> list:
    """Return the most recent N entries, newest first."""
    if not os.path.exists(ACTIVITY_FILE):
        return []
    try:
        with open(ACTIVITY_FILE, "r", encoding="utf-8") as f:
            lines = [l.rstrip() for l in f.readlines() if l.strip()]
        return list(reversed(lines[-n:]))
    except OSError:
        return []


def clear() -> None:
    """Wipe the activity log."""
    try:
        open(ACTIVITY_FILE, "w").close()
    except OSError:
        pass


def _trim() -> None:
    """Keep only the last MAX_LINES entries so the file stays small."""
    try:
        with open(ACTIVITY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > MAX_LINES:
            with open(ACTIVITY_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines[-MAX_LINES:])
    except OSError:
        pass
