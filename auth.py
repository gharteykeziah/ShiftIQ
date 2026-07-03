"""
auth.py — Password hashing and JWT token utilities.

This module is the single source of truth for all authentication logic.
Nothing outside this file calls bcrypt or python-jose directly.

Four public functions:
    hash_password(plain)          -> hashed string to store in DB
    verify_password(plain, hashed)-> True/False
    create_token(user_id)         -> signed JWT string
    decode_token(token)           -> user_id int, or raises HTTPException 401

Security rules enforced here:
  - Passwords are NEVER logged, printed, or returned in any response.
  - The SECRET_KEY is read from the environment — never hardcoded.
  - The app refuses to start if SECRET_KEY is missing or too short.
  - Tokens expire after TOKEN_EXPIRE_DAYS days.
  - A tampered, expired, or missing token always raises HTTP 401.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt

# ── Config ────────────────────────────────────────────────────────────────────

ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7

# Secret key used to sign JWT tokens.
# Must be set in the environment (.env locally, env var in production).
# Generate a strong one with: python -c "import secrets; print(secrets.token_hex(32))"
_SECRET_KEY: str = os.getenv("SECRET_KEY", "")

if not _SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. "
        "Add it to your .env file for local dev, or set it in your cloud "
        "environment for production. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )

if len(_SECRET_KEY) < 32:
    raise RuntimeError(
        f"SECRET_KEY is too short ({len(_SECRET_KEY)} chars). "
        "Use at least 32 characters to ensure token security."
    )

# ── Password hashing ──────────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    """Hash a plain-text password with bcrypt.

    The returned string is safe to store in the database.
    The original password is never stored anywhere.

    Args:
        plain: The user's plain-text password.

    Returns:
        A bcrypt hash string (e.g. "$2b$12$...").
    """
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plain-text password against a stored bcrypt hash.

    Args:
        plain:  The password the user typed at login.
        hashed: The hash stored in the database for that user.

    Returns:
        True if the password matches, False otherwise.
    """
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT tokens ────────────────────────────────────────────────────────────────

def create_token(user_id: int) -> str:
    """Create a signed JWT access token for the given user.

    The token encodes the user_id and an expiry timestamp.
    It is signed with SECRET_KEY using HS256 — any tampering
    will cause decode_token to reject it.

    Args:
        user_id: The database ID of the authenticated user.

    Returns:
        A signed JWT string to return to the client.
    """
    expire = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),   # "subject" — standard JWT claim for the user ID
        "exp": expire,          # expiry — python-jose enforces this automatically
    }
    return jwt.encode(payload, _SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> int:
    """Decode and verify a JWT access token.

    Raises HTTP 401 if the token is missing, expired, or tampered with.
    Never returns partial data from an invalid token.

    Args:
        token: The raw JWT string from the Authorization header.

    Returns:
        The user_id (int) encoded in the token.

    Raises:
        HTTPException 401: If the token is invalid for any reason.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise credentials_error
        return int(user_id_str)
    except (JWTError, ValueError):
        raise credentials_error
