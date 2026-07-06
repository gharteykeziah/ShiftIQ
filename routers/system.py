"""routers/system.py — endpoints outside the 7 named domains.

health, privacy (JSON + HTML), state, balance, history, and projection don't
map onto auth/jobs/shifts/expenses/optimizer/simulation/insights, so they get
one router of their own rather than being forced into the wrong domain.
No shared prefix (paths don't share a common root, and /privacy has no /api
prefix at all — preserved exactly as it was in api.py).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse

import privacy_policy
from dependencies import get_current_user, limiter
from schemas import BalanceIn, StateSummary
from services import state_service

router = APIRouter(tags=["system"])


@router.get("/api/health")
@limiter.limit("60/minute")
def health(request: Request) -> dict:
    return {"status": "ok"}


@router.get("/api/privacy")
@limiter.limit("60/minute")
def get_privacy_json(request: Request) -> dict:
    """Return the privacy policy as structured JSON."""
    return privacy_policy.as_dict()


@router.get("/privacy", response_class=FileResponse)
@limiter.limit("60/minute")
def get_privacy_html(request: Request):
    """Return the privacy policy as a human-readable HTML page."""
    return HTMLResponse(content=privacy_policy.as_html(), status_code=200)


@router.get("/api/state", response_model=StateSummary)
@limiter.limit("60/minute")
def get_state_summary(request: Request, current_user: dict = Depends(get_current_user)) -> StateSummary:
    return state_service.get_state_summary(current_user["id"])


@router.put("/api/balance")
@limiter.limit("30/minute")
def update_balance(request: Request, body: BalanceIn, current_user: dict = Depends(get_current_user)) -> dict:
    """Update the current saved balance."""
    return state_service.update_balance(current_user["id"], body.amount)


@router.get("/api/history")
@limiter.limit("60/minute")
def get_history(request: Request, current_user: dict = Depends(get_current_user)) -> dict:
    return state_service.get_history(current_user["id"])


@router.get("/api/projection")
@limiter.limit("60/minute")
def get_projection(
    request: Request, weeks: int = 12, current_user: dict = Depends(get_current_user),
) -> dict:
    """Project balance week-by-week over the next N weeks (default 12)."""
    return state_service.get_projection(current_user["id"], weeks)
