"""routers/auth.py — /api/auth/register, /api/auth/login, /api/auth/me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from backend.core.dependencies import get_current_user, limiter
from backend.core.schemas import LoginIn, RegisterIn
from backend.api.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=201)
@limiter.limit("5/minute")
def register(request: Request, body: RegisterIn) -> dict:
    """Create a new user account. Returns 409 if the email is already taken."""
    return auth_service.register_user(body.email, body.password)


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, body: LoginIn) -> dict:
    """Authenticate a user and return a signed JWT access token."""
    return auth_service.authenticate_user(body.email, body.password)


@router.get("/me")
@limiter.limit("60/minute")
def me(request: Request, current_user: dict = Depends(get_current_user)) -> dict:
    """Return the currently authenticated user's profile."""
    return auth_service.get_profile(current_user)
