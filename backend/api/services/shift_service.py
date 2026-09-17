"""
services/shift_service.py — CRUD business logic for shifts.

Moved verbatim out of api.py's list_shifts()/create_shift()/update_shift()/delete_shift().
The inline `from backend.core.schedule_event import ScheduleEvent` import is hoisted to
module level here — same module, same class, evaluated once at import time
instead of once per request. No behavior change.
"""
from __future__ import annotations

from fastapi import HTTPException

import backend.core.database as db
from backend.core.schedule_event import ScheduleEvent
from backend.core.schemas import ShiftIn, ShiftOut
from backend.core.validation import VALID_DAYS


def _event_to_out(event) -> ShiftOut:
    return ShiftOut(
        id=event.id, title=event.title, category=event.category, day=event.day,
        start_time=event.start_time, end_time=event.end_time,
        hourly_rate=event.hourly_rate, notes=event.notes, shift_date=event.shift_date,
    )


def list_shifts(user_id: int, day: str | None) -> list[ShiftOut]:
    if day and day not in VALID_DAYS:
        raise HTTPException(status_code=400, detail=f"day must be one of {sorted(VALID_DAYS)}")
    events = db.get_events(day=day, user_id=user_id)
    return [_event_to_out(e) for e in events]


def create_shift(user_id: int, shift_in: ShiftIn) -> ShiftOut:
    event = ScheduleEvent(
        title=shift_in.title, category=shift_in.category, day=shift_in.day,
        start_time=shift_in.start_time, end_time=shift_in.end_time,
        hourly_rate=shift_in.hourly_rate, notes=shift_in.notes,
        shift_date=shift_in.shift_date,
    )
    ok, msg = event.validate()
    if not ok:
        raise HTTPException(status_code=422, detail=msg)
    new_id = db.add_event(event, user_id=user_id)
    return ShiftOut(
        id=new_id, title=event.title, category=event.category, day=event.day,
        start_time=event.start_time, end_time=event.end_time,
        hourly_rate=event.hourly_rate, notes=event.notes, shift_date=event.shift_date,
    )


def update_shift(user_id: int, shift_id: int, shift_in: ShiftIn) -> ShiftOut:
    """Returns 404 if the shift doesn't exist or belongs to another user."""
    existing = db.get_event_by_id(shift_id, user_id=user_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Shift not found.")
    event = ScheduleEvent(
        title=shift_in.title, category=shift_in.category, day=shift_in.day,
        start_time=shift_in.start_time, end_time=shift_in.end_time,
        hourly_rate=shift_in.hourly_rate, notes=shift_in.notes,
        shift_date=shift_in.shift_date,
    )
    ok, msg = event.validate()
    if not ok:
        raise HTTPException(status_code=422, detail=msg)
    db.update_event(
        shift_id,
        title=event.title, category=event.category, day=event.day,
        start_time=event.start_time, end_time=event.end_time,
        hourly_rate=event.hourly_rate, notes=event.notes, shift_date=event.shift_date,
    )
    return ShiftOut(
        id=shift_id, title=event.title, category=event.category, day=event.day,
        start_time=event.start_time, end_time=event.end_time,
        hourly_rate=event.hourly_rate, notes=event.notes, shift_date=event.shift_date,
    )


def delete_shift(user_id: int, shift_id: int) -> None:
    """Returns 404 if the shift doesn't exist or belongs to another user."""
    existing = db.get_event_by_id(shift_id, user_id=user_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Shift not found.")
    db.delete_event_by_id(shift_id)
