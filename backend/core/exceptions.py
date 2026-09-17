"""
exceptions.py — Shared exception classes for ShiftIQ.

Import from here so every module uses the same exception hierarchy.
"""


class ValidationError(Exception):
    """Raised when user-supplied input fails a business-rule check."""
