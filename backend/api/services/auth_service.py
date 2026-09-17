"""
services/auth_service.py — Registration, login, and profile lookup.

Moved verbatim out of api.py's register()/login()/me() route bodies.
"""
from __future__ import annotations

from fastapi import HTTPException

import backend.core.auth as auth
import backend.core.database as db


def register_user(email: str, password: str) -> dict:
    """Create a new user account.

    Validates email format and password length were already enforced by
    RegisterIn; here we check for a duplicate email, hash the password with
    bcrypt, then store the user. Returns 409 if the email is already taken.
    Never returns the password or hash.
    """
    existing = db.get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered.")

    hashed = auth.hash_password(password)
    db.insert_user(email, hashed)

    return {"message": "Account created.", "email": email}


def authenticate_user(email: str, password: str) -> dict:
    """Authenticate a user and return a signed JWT access token.

    Security rules:
    - Wrong email and wrong password return the SAME error message.
      This prevents user enumeration (attacker can't tell which was wrong).
    - Token contains only user_id — no email, no password, no sensitive data.
    - Token expires after 7 days (configured in auth.py).
    """
    _invalid = HTTPException(status_code=401, detail="Invalid email or password.")

    user = db.get_user_by_email(email)
    if user is None:
        raise _invalid

    if not auth.verify_password(password, user["hashed_password"]):
        raise _invalid

    token = auth.create_token(user["id"])
    return {"access_token": token, "token_type": "bearer"}


def get_profile(current_user: dict) -> dict:
    """Return id, email, and created_at — never the hashed_password."""
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "created_at": current_user["created_at"],
    }
