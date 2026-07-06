"""routers/jobs.py — /api/jobs CRUD."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from dependencies import get_current_user, limiter
from schemas import JobIn, JobOut
from services import job_service

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
@limiter.limit("60/minute")
def list_jobs(request: Request, current_user: dict = Depends(get_current_user)) -> list[JobOut]:
    return job_service.list_jobs(current_user["id"])


@router.post("", response_model=JobOut, status_code=201)
@limiter.limit("30/minute")
def add_job(request: Request, job_in: JobIn, current_user: dict = Depends(get_current_user)) -> JobOut:
    return job_service.add_job(current_user["id"], job_in.name, job_in.amount, job_in.frequency)


@router.put("/{name}", response_model=JobOut)
@limiter.limit("30/minute")
def update_job(
    request: Request, name: str, job_in: JobIn, current_user: dict = Depends(get_current_user),
) -> JobOut:
    """Update an existing job's amount and/or frequency by name."""
    return job_service.update_job(current_user["id"], name, job_in.name, job_in.amount, job_in.frequency)


@router.delete("/{name}")
@limiter.limit("30/minute")
def delete_job(request: Request, name: str, current_user: dict = Depends(get_current_user)) -> dict:
    return job_service.delete_job(current_user["id"], name)
