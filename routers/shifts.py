"""routers/shifts.py — /api/shifts CRUD."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request

from dependencies import get_current_user, limiter
from schemas import ShiftIn, ShiftOut
from services import shift_service

router = APIRouter(prefix="/api/shifts", tags=["shifts"])


@router.get("", response_model=list[ShiftOut])
@limiter.limit("60/minute")
def list_shifts(
    request: Request,
    day: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
) -> list[ShiftOut]:
    """Return all shifts for the current user. Optional ?day= filter (e.g. Monday)."""
    return shift_service.list_shifts(current_user["id"], day)


@router.post("", response_model=ShiftOut, status_code=201)
@limiter.limit("30/minute")
def create_shift(
    request: Request,
    shift_in: ShiftIn,
    current_user: dict = Depends(get_current_user),
) -> ShiftOut:
    """Create a new shift for the current user."""
    return shift_service.create_shift(current_user["id"], shift_in)


@router.put("/{shift_id}", response_model=ShiftOut)
@limiter.limit("30/minute")
def update_shift(
    request: Request,
    shift_id: int,
    shift_in: ShiftIn,
    current_user: dict = Depends(get_current_user),
) -> ShiftOut:
    """Update a shift. Returns 404 if the shift doesn't exist or belongs to another user."""
    return shift_service.update_shift(current_user["id"], shift_id, shift_in)


@router.delete("/{shift_id}", status_code=204)
@limiter.limit("30/minute")
def delete_shift(
    request: Request,
    shift_id: int,
    current_user: dict = Depends(get_current_user),
) -> None:
    """Delete a shift. Returns 404 if it doesn't exist or belongs to another user."""
    shift_service.delete_shift(current_user["id"], shift_id)
