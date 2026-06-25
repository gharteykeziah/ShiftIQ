"""
utils.py — Shared utility functions for the ShiftIQ.

Single source of truth for name canonicalization.
All modules must import from here — never define _canon() locally.
"""

from __future__ import annotations
from difflib import SequenceMatcher


def canon_name(name: str) -> str:
    """
    Canonical job/expense name.
    strip → drop trailing 's' if stem is > 4 chars → Title Case.

    Examples:
        'admissions'  → 'Admission'
        'Admissions'  → 'Admission'
        'ADMISSIONS'  → 'Admission'
        'OIP'         → 'Oip'   (len == 3, no strip)
        'jobs'        → 'Job'
        'Rent'        → 'Rent'  (no trailing s)
    """
    n = name.strip()
    if len(n) > 4 and n.lower().endswith("s"):
        n = n[:-1]
    return n.title()


def normalize_job_name(raw: str, existing_names: list[str]) -> str:
    """
    Resolve a raw job-name string to the canonical name already stored.

    Resolution order:
      1. Exact match (case-insensitive)     → return stored name
      2. canon_name() key match             → return stored name
      3. Fuzzy (SequenceMatcher ≥ 0.82)     → return stored name
      4. No match                           → canon_name(raw)

    Always returns the *stored* canonical spelling so displays are consistent.
    """
    raw_stripped = raw.strip()
    if not raw_stripped:
        return raw_stripped

    raw_lower = raw_stripped.lower()
    raw_key   = canon_name(raw_stripped)

    best_ratio = 0.0
    best_name  = None

    for name in existing_names:
        # 1. Exact (case-insensitive)
        if name.lower() == raw_lower:
            return name
        # 2. Canon-key match
        if canon_name(name) == raw_key:
            return name
        # 3. Track best fuzzy score
        ratio = SequenceMatcher(None, raw_lower, name.lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_name  = name

    # 3. Accept fuzzy match if above threshold
    if best_ratio >= 0.82 and best_name:
        return best_name

    # 4. New name — use canon form
    return canon_name(raw_stripped)
