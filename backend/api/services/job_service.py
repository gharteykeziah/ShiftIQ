"""
services/job_service.py — CRUD business logic for jobs.

Moved verbatim out of api.py's list_jobs()/add_job()/update_job()/delete_job().
"""
from __future__ import annotations

from fastapi import HTTPException

import backend.core.database as db
from backend.core.dependencies import get_state
from backend.core.model import Job
from backend.core.schemas import JobOut


def _to_out(job: Job) -> JobOut:
    return JobOut(
        name=job.name, amount=job.amount, frequency=job.frequency,
        weekly_income=round(job.weekly_income(), 2),
    )


def list_jobs(user_id: int) -> list[JobOut]:
    return [_to_out(j) for j in db.load_jobs(user_id=user_id)]


def add_job(user_id: int, name: str, amount: float, frequency: str) -> JobOut:
    state = get_state(user_id)
    job = Job(name, amount, frequency)
    ok, message = state.add_job(job)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return _to_out(job)


def update_job(user_id: int, name: str, new_name: str, amount: float, frequency: str) -> JobOut:
    """If renaming (new_name != name), checks that the new name is not already
    taken BEFORE deleting the old record, preventing silent data loss."""
    state = get_state(user_id)
    if new_name != name and any(j.name == new_name for j in state.jobs):
        raise HTTPException(status_code=400, detail=f"A job named '{new_name}' already exists.")
    ok, message = state.delete_job(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Job '{name}' not found.")
    job = Job(new_name, amount, frequency)
    ok, message = state.add_job(job)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return _to_out(job)


def delete_job(user_id: int, name: str) -> dict:
    state = get_state(user_id)
    ok, message = state.delete_job(name)
    if not ok:
        raise HTTPException(status_code=404, detail=message)
    return {"message": message}
