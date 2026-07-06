"""
dependencies.py — Cross-cutting request dependencies shared by every router.

Holds the pieces that don't belong to any single domain: the rate-limiter
instance (routers decorate their own endpoints with it; api.py re-exports it
so `from api import limiter` keeps working for test_api.py), the Bearer-token
auth dependency, and the per-request FinancialState factory. None of this is
business logic — it's plumbing used by auth, jobs, shifts, expenses,
optimizer, simulation, insights, and system.

Moved verbatim out of api.py — no behavior changed.
"""
from __future__ import annotations

from fastapi import Header, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address

import auth
import database as db
from financial_state import FinancialState

# Keys requests by IP address. Limits:
#   - Auth endpoints: 10/minute  (slow down password-guessing attacks)
#   - Write endpoints: 30/minute (prevent bulk data abuse)
#   - Read endpoints:  60/minute (comfortable for real users, not for scrapers)
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency — extract and verify the Bearer token.

    Attach to any endpoint that requires authentication:
        current_user: dict = Depends(get_current_user)

    Returns the user dict {id, email, created_at} on success.
    Raises HTTP 401 if the header is missing, malformed, expired, or invalid.
    The hashed_password is intentionally excluded from the returned dict.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[len("Bearer "):].strip()
    user_id = auth.decode_token(token)   # raises 401 if expired or tampered
    user = db.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User account not found.")
    return user


def get_state(user_id: int = 1) -> FinancialState:
    """Fresh FinancialState per request, scoped to the given user.

    SQLite is the single source of truth, so there is no in-memory state
    to keep consistent across requests. user_id defaults to 1 so the
    desktop app (which never passes a token) still works unchanged.
    """
    return FinancialState(user_id=user_id)
