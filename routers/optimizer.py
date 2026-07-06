"""routers/optimizer.py — /api/optimize/shifts."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from dependencies import get_current_user, limiter
from schemas import OptimizeRequest
from services import optimizer_service

router = APIRouter(prefix="/api/optimize", tags=["optimizer"])


@router.post("/shifts")
@limiter.limit("20/minute")
def optimize_shifts(
    request: Request, req: OptimizeRequest, current_user: dict = Depends(get_current_user),
) -> dict:
    return optimizer_service.optimize_shifts(current_user["id"], req.max_hours)
