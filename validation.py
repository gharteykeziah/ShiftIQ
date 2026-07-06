"""
validation.py — Shared input-sanitization helpers and allow-list constants.

Pure functions and constants, no I/O, no business logic. Extracted out of
api.py so both schemas.py (Pydantic field validators) and the routers that
also validate query parameters (e.g. routers/shifts.py's ?day= filter) use
exactly one copy of each rule instead of duplicating it.
"""
from __future__ import annotations

import re

_HTML_TAG_RE = re.compile(r'<[^>]+>')


def strip_html(value: str) -> str:
    """Remove all HTML/script tags from a string and strip surrounding whitespace.

    This is the first line of defence against XSS: anything a user types that
    contains <script>, <img onerror=...>, or any other tag is stripped before
    it ever reaches the database or gets echoed back in a response.
    """
    return _HTML_TAG_RE.sub('', value).strip()


# Must match FREQ_TO_WEEKLY keys in model.py exactly — wrong values silently
# fall back to a 1.0 multiplier and produce incorrect income projections.
VALID_FREQUENCIES = {"Daily", "Weekly", "Biweekly", "Monthly"}

VALID_CATEGORIES = {"Work", "Class", "Study", "Meeting", "Personal", "Other"}

VALID_DAYS = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
