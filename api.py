"""
api.py — FastAPI service exposing the ShiftIQ engine over HTTP.

This is a thin transport layer only. It contains zero financial logic —
every endpoint is a direct pass-through to the same engine modules the
desktop app uses (financial_state.py, simulation.py,
shift_analytics.py, optimizer.py, database.py). That is the same
UI / business-logic separation the rest of the project enforces: the
desktop app and this API are two different front ends on top of one
unmodified engine.

Run locally:
    pip install -r requirements.txt
    pip install fastapi "uvicorn[standard]" pydantic
    uvicorn api:app --reload

Then open http://127.0.0.1:8000 for the thin built-in frontend, or
http://127.0.0.1:8000/docs for interactive Swagger API docs (generated
automatically by FastAPI from the type hints below).
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
load_dotenv()  # loads .env when running locally; no-op in production

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import auth
import database as db
import db_pg
import privacy_policy
from db_connection import get_connection, is_postgres
from financial_state import FinancialState
from insight_engine import InsightEngine
from simulation import run_monte_carlo, simulate_whatif
from optimizer import optimize_shift_selection, candidates_from_events
import shift_analytics as sa
from model import Job, Expense
from config import MONTE_CARLO_RUNS, CORS_ORIGINS

# ── Rate limiter ──────────────────────────────────────────────────────────────
# Keys requests by IP address. Limits:
#   - Auth endpoints: 10/minute  (slow down password-guessing attacks)
#   - Write endpoints: 30/minute (prevent bulk data abuse)
#   - Read endpoints:  60/minute (comfortable for real users, not for scrapers)
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(
    title="ShiftIQ API",
    description="Schedule-driven financial simulation engine, exposed over HTTP.",
    version="2.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Allow only known frontend origins to call the API — configured via the
# CORS_ORIGINS env var (comma-separated). Defaults to the standard Next.js
# dev server origins (http://localhost:3000, http://127.0.0.1:3000) when
# unset. Production deployments MUST set CORS_ORIGINS to the real frontend
# domain(s), e.g. CORS_ORIGINS=https://app.shiftiq.com
#
# A wildcard ("*") is refused outright — it would let any website read
# authenticated responses via a stolen/copied Bearer token in a user's
# browser (e.g. via a malicious script making a fetch() from another tab).
# Scoping to explicit origins costs nothing since the frontend origin is
# known ahead of time, and it's the only one that should ever call this API.
#
# allow_credentials=False: this API uses Bearer tokens in the Authorization
# header, not cookies. allow_credentials=True is only required for
# cookie-based auth.
if "*" in CORS_ORIGINS:
    raise RuntimeError(
        "CORS_ORIGINS cannot include '*'. Set it to a comma-separated list "
        "of exact frontend origins, e.g. "
        "CORS_ORIGINS=https://app.shiftiq.com,http://localhost:3000"
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Security headers ──────────────────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security headers to every HTTP response.

    These headers instruct browsers to block common attack vectors:
    - nosniff:     prevent MIME-type sniffing (browser executing JSON as script)
    - DENY:        block clickjacking via <iframe> embedding
    - XSS-filter:  activate the browser's built-in XSS detector (legacy browsers)
    - Referrer:    don't leak URL details to third-party sites
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


app.add_middleware(SecurityHeadersMiddleware)

_insight_engine = InsightEngine()


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
def _startup() -> None:
    """
    Initialise the database on startup.

    - DATABASE_URL not set  →  SQLite via database.init_db()
    - DATABASE_URL set      →  PostgreSQL via db_pg.init_db()

    No other code needs to know which backend is active — get_connection()
    handles that transparently for every query.
    """
    if is_postgres():
        with get_connection() as conn:
            db_pg.init_db(conn)
    else:
        db.init_db()
        db.init_events_table()


def _get_state(user_id: int = 1) -> FinancialState:
    """Fresh FinancialState per request, scoped to the given user.

    SQLite is the single source of truth, so there is no in-memory state
    to keep consistent across requests. user_id defaults to 1 so the
    desktop app (which never passes a token) still works unchanged.
    """
    return FinancialState(user_id=user_id)


# ── Input sanitization helper ─────────────────────────────────────────────────

_HTML_TAG_RE = re.compile(r'<[^>]+>')

def _strip_html(value: str) -> str:
    """Remove all HTML/script tags from a string and strip surrounding whitespace.

    This is the first line of defence against XSS: anything a user types that
    contains <script>, <img onerror=...>, or any other tag is stripped before
    it ever reaches the database or gets echoed back in a response.
    """
    return _HTML_TAG_RE.sub('', value).strip()


# Must match FREQ_TO_WEEKLY keys in model.py exactly — wrong values silently
# fall back to a 1.0 multiplier and produce incorrect income projections.
_VALID_FREQUENCIES = {"Daily", "Weekly", "Biweekly", "Monthly"}


# ── Schemas ───────────────────────────────────────────────────────────────────

class JobIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0, le=1_000_000)
    frequency: str = "Weekly"

    @field_validator("name", mode="before")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        v = _strip_html(str(v))
        if not v:
            raise ValueError("name cannot be empty")
        return v

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        if v not in _VALID_FREQUENCIES:
            raise ValueError(f"frequency must be one of {sorted(_VALID_FREQUENCIES)}")
        return v


class JobOut(BaseModel):
    name: str
    amount: float
    frequency: str
    weekly_income: float


class ExpenseIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0, le=1_000_000)
    category: str = Field(min_length=1, max_length=50)
    date: str
    frequency: str = "Monthly"

    @field_validator("name", "category", mode="before")
    @classmethod
    def sanitize_strings(cls, v: str) -> str:
        v = _strip_html(str(v))
        if not v:
            raise ValueError("field cannot be empty")
        return v

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("date must be in YYYY-MM-DD format")
        return v

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        if v not in _VALID_FREQUENCIES:
            raise ValueError(f"frequency must be one of {sorted(_VALID_FREQUENCIES)}")
        return v


class ExpenseOut(BaseModel):
    name: str
    amount: float
    category: str
    date: str
    frequency: str
    weekly_amount: float


class StateSummary(BaseModel):
    balance: float
    weekly_income: float
    weekly_expenses: float
    net_weekly_flow: float
    savings_rate: float
    risk_score: int
    health_score: int


class BalanceIn(BaseModel):
    amount: float = Field(ge=0, le=100_000_000, description="New balance in dollars (must be 0 or greater)")


class MonteCarloRequest(BaseModel):
    weeks: int = Field(gt=0, le=520)
    n: int = Field(default=MONTE_CARLO_RUNS, gt=0, le=10_000)


class WhatIfRequest(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    dollar_change: float = Field(ge=-1_000_000, le=1_000_000)
    weeks: int = Field(gt=0, le=520)

    @field_validator("description", mode="before")
    @classmethod
    def sanitize_description(cls, v: str) -> str:
        v = _strip_html(str(v))
        if not v:
            raise ValueError("description cannot be empty")
        return v


class OptimizeRequest(BaseModel):
    max_hours: float = Field(gt=0, le=168)


class RegisterIn(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        import re
        v = v.lower().strip()
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', v):
            raise ValueError("invalid email address")
        return v

    @field_validator("password")
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        # Length is enforced by Field(min_length=8) — this strips whitespace-only
        if not v.strip():
            raise ValueError("password cannot be blank")
        return v


class LoginIn(BaseModel):
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.lower().strip()


_VALID_CATEGORIES = {"Work", "Class", "Study", "Meeting", "Personal", "Other"}
_VALID_DAYS = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}


class ShiftIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    category: str = "Work"
    day: str = "Monday"
    start_time: str = "09:00"
    end_time: str = "17:00"
    hourly_rate: float = Field(default=0.0, ge=0, le=10_000)
    notes: str = Field(default="", max_length=500)
    shift_date: str = ""

    @field_validator("title", mode="before")
    @classmethod
    def sanitize_title(cls, v: str) -> str:
        v = _strip_html(str(v))
        if not v:
            raise ValueError("title cannot be empty")
        return v

    @field_validator("notes", mode="before")
    @classmethod
    def sanitize_notes(cls, v: str) -> str:
        return _strip_html(str(v))

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in _VALID_CATEGORIES:
            raise ValueError(f"category must be one of {sorted(_VALID_CATEGORIES)}")
        return v

    @field_validator("day")
    @classmethod
    def validate_day(cls, v: str) -> str:
        if v not in _VALID_DAYS:
            raise ValueError(f"day must be one of {sorted(_VALID_DAYS)}")
        return v

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time(cls, v: str) -> str:
        import re as _re
        if not _re.match(r'^\d{2}:\d{2}$', v):
            raise ValueError("time must be in HH:MM format")
        h, m = int(v[:2]), int(v[3:])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("invalid time value")
        return v

    @field_validator("shift_date")
    @classmethod
    def validate_shift_date(cls, v: str) -> str:
        if v:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError("shift_date must be in YYYY-MM-DD format")
        return v


class ShiftOut(BaseModel):
    id: int
    title: str
    category: str
    day: str
    start_time: str
    end_time: str
    hourly_rate: float
    notes: str
    shift_date: str


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
@limiter.limit("60/minute")
def health(request: Request) -> dict:
    return {"status": "ok"}


# ── Privacy policy ────────────────────────────────────────────────────────────

@app.get("/api/privacy")
@limiter.limit("60/minute")
def get_privacy_json(request: Request) -> dict:
    """Return the privacy policy as structured JSON."""
    return privacy_policy.as_dict()


@app.get("/privacy", response_class=FileResponse)
@limiter.limit("60/minute")
def get_privacy_html(request: Request):
    """Return the privacy policy as a human-readable HTML page."""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=privacy_policy.as_html(), status_code=200)


# ── Auth ─────────────────────────────────────────────────────────────────────

@app.post("/api/auth/register", status_code=201)
@limiter.limit("5/minute")
def register(request: Request, body: RegisterIn) -> dict:
    """Create a new user account.

    Validates email format and password length, hashes the password with
    bcrypt, then stores the user. Returns 409 if the email is already taken.
    Never returns the password or hash in the response.
    """
    # Check for duplicate email before inserting
    existing = db.get_user_by_email(body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered.")

    hashed = auth.hash_password(body.password)
    db.insert_user(body.email, hashed)

    return {"message": "Account created.", "email": body.email}


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


@app.post("/api/auth/login")
@limiter.limit("10/minute")
def login(request: Request, body: LoginIn) -> dict:
    """Authenticate a user and return a signed JWT access token.

    Security rules:
    - Wrong email and wrong password return the SAME error message.
      This prevents user enumeration (attacker can't tell which was wrong).
    - Rate limited to 10/minute to block brute-force password guessing.
    - Token contains only user_id — no email, no password, no sensitive data.
    - Token expires after 7 days (configured in auth.py).
    """
    _invalid = HTTPException(
        status_code=401,
        detail="Invalid email or password.",
    )

    user = db.get_user_by_email(body.email)
    if user is None:
        raise _invalid

    if not auth.verify_password(body.password, user["hashed_password"]):
        raise _invalid

    token = auth.create_token(user["id"])
    return {"access_token": token, "token_type": "bearer"}


@app.get("/api/auth/me")
@limiter.limit("60/minute")
def me(request: Request, current_user: dict = Depends(get_current_user)) -> dict:
    """Return the currently authenticated user's profile.

    Requires a valid Bearer token in the Authorization header.
    Returns id, email, and created_at — never the hashed_password.
    """
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "created_at": current_user["created_at"],
    }


# ── Financial state ───────────────────────────────────────────────────────────

@app.get("/api/state", response_model=StateSummary)
@limiter.limit("60/minute")
def get_state_summary(request: Request, current_user: dict = Depends(get_current_user)) -> StateSummary:
    state = _get_state(current_user["id"])
    return StateSummary(
        balance=state.current_balance(),
        weekly_income=round(state.total_income_per_week(), 2),
        weekly_expenses=round(state.total_expense_per_week(), 2),
        net_weekly_flow=round(state.net_weekly_flow(), 2),
        savings_rate=round(state.savings_rate(), 4),
        risk_score=state.risk_score(),
        health_score=state.financial_health_score(),
    )


# ── Balance ───────────────────────────────────────────────────────────────────

@app.put("/api/balance")
@limiter.limit("30/minute")
def update_balance(request: Request, body: BalanceIn, current_user: dict = Depends(get_current_user)) -> dict:
    """Update the current saved balance."""
    state = _get_state(current_user["id"])
    ok, message = state.set_balance(body.amount)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"balance": body.amount, "message": message}


# ── Jobs ──────────────────────────────────────────────────────────────────────

@app.get("/api/jobs", response_model=list[JobOut])
@limiter.limit("60/minute")
def list_jobs(request: Request, current_user: dict = Depends(get_current_user)) -> list[JobOut]:
    return [
        JobOut(name=j.name, amount=j.amount, frequency=j.frequency,
               weekly_income=round(j.weekly_income(), 2))
        for j in db.load_jobs(user_id=current_user["id"])
    ]


@app.post("/api/jobs", response_model=JobOut, status_code=201)
@limiter.limit("30/minute")
def add_job(request: Request, job_in: JobIn, current_user: dict = Depends(get_current_user)) -> JobOut:
    state = _get_state(current_user["id"])
    job = Job(job_in.name, job_in.amount, job_in.frequency)
    ok, message = state.add_job(job)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return JobOut(name=job.name, amount=job.amount, frequency=job.frequency,
                  weekly_income=round(job.weekly_income(), 2))


@app.put("/api/jobs/{name}", response_model=JobOut)
@limiter.limit("30/minute")
def update_job(request: Request, name: str, job_in: JobIn, current_user: dict = Depends(get_current_user)) -> JobOut:
    """Update an existing job's amount and/or frequency by name.

    If renaming (job_in.name != name), checks that the new name is not already
    taken BEFORE deleting the old record, preventing silent data loss.
    """
    state = _get_state(current_user["id"])
    # Safety: if renaming, verify the target name doesn't already exist
    if job_in.name != name and any(j.name == job_in.name for j in state.jobs):
        raise HTTPException(status_code=400, detail=f"A job named '{job_in.name}' already exists.")
    ok, message = state.delete_job(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Job '{name}' not found.")
    job = Job(job_in.name, job_in.amount, job_in.frequency)
    ok, message = state.add_job(job)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return JobOut(name=job.name, amount=job.amount, frequency=job.frequency,
                  weekly_income=round(job.weekly_income(), 2))


@app.delete("/api/jobs/{name}")
@limiter.limit("30/minute")
def delete_job(request: Request, name: str, current_user: dict = Depends(get_current_user)) -> dict:
    state = _get_state(current_user["id"])
    ok, message = state.delete_job(name)
    if not ok:
        raise HTTPException(status_code=404, detail=message)
    return {"message": message}


# ── Expenses ──────────────────────────────────────────────────────────────────

@app.get("/api/expenses", response_model=list[ExpenseOut])
@limiter.limit("60/minute")
def list_expenses(request: Request, current_user: dict = Depends(get_current_user)) -> list[ExpenseOut]:
    return [
        ExpenseOut(name=e.name, amount=e.amount, category=e.category,
                   date=e.date, frequency=e.frequency,
                   weekly_amount=round(e.weekly_amount(), 2))
        for e in db.load_expenses(user_id=current_user["id"])
    ]


@app.post("/api/expenses", response_model=ExpenseOut, status_code=201)
@limiter.limit("30/minute")
def add_expense(request: Request, expense_in: ExpenseIn, current_user: dict = Depends(get_current_user)) -> ExpenseOut:
    state = _get_state(current_user["id"])
    expense = Expense(expense_in.name, expense_in.amount, expense_in.category,
                       expense_in.date, expense_in.frequency)
    ok, message = state.add_expense(expense)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return ExpenseOut(name=expense.name, amount=expense.amount,
                      category=expense.category, date=expense.date,
                      frequency=expense.frequency,
                      weekly_amount=round(expense.weekly_amount(), 2))


@app.put("/api/expenses/{name}", response_model=ExpenseOut)
@limiter.limit("30/minute")
def update_expense(request: Request, name: str, expense_in: ExpenseIn, current_user: dict = Depends(get_current_user)) -> ExpenseOut:
    """Update an existing expense by name.

    If renaming (expense_in.name != name), checks that the new name is not
    already taken BEFORE deleting the old record, preventing silent data loss.
    """
    state = _get_state(current_user["id"])
    # Safety: if renaming, verify the target name doesn't already exist
    if expense_in.name != name and any(e.name == expense_in.name for e in state.expenses):
        raise HTTPException(status_code=400, detail=f"An expense named '{expense_in.name}' already exists.")
    ok, message = state.delete_expense(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Expense '{name}' not found.")
    expense = Expense(expense_in.name, expense_in.amount, expense_in.category,
                      expense_in.date, expense_in.frequency)
    ok, message = state.add_expense(expense)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return ExpenseOut(name=expense.name, amount=expense.amount,
                      category=expense.category, date=expense.date,
                      frequency=expense.frequency,
                      weekly_amount=round(expense.weekly_amount(), 2))


@app.delete("/api/expenses/{name}")
@limiter.limit("30/minute")
def delete_expense(request: Request, name: str, current_user: dict = Depends(get_current_user)) -> dict:
    state = _get_state(current_user["id"])
    ok, message = state.delete_expense(name)
    if not ok:
        raise HTTPException(status_code=404, detail=message)
    return {"message": message}


# ── History ───────────────────────────────────────────────────────────────────

@app.get("/api/history")
@limiter.limit("60/minute")
def get_history(request: Request, current_user: dict = Depends(get_current_user)) -> dict:
    """Return all daily financial snapshots ordered by date ascending."""
    snapshots = db.load_history(user_id=current_user["id"])
    return {
        "count": len(snapshots),
        "snapshots": snapshots,
    }


# ── Insights ──────────────────────────────────────────────────────────────────

@app.get("/api/insights")
@limiter.limit("60/minute")
def get_insights(request: Request, current_user: dict = Depends(get_current_user)) -> dict:
    """Return plain-English financial insights generated by the InsightEngine."""
    state = _get_state(current_user["id"])
    insights = _insight_engine.generate_insights(state)
    return {
        "health_score": state.financial_health_score(),
        "risk_score": state.risk_score(),
        "health_label": _insight_engine.health_label(state.financial_health_score()),
        "risk_label": _insight_engine.risk_label(state.risk_score()),
        "insights": insights,
    }


# ── Projection ────────────────────────────────────────────────────────────────

@app.get("/api/projection")
@limiter.limit("60/minute")
def get_projection(request: Request, weeks: int = 12, current_user: dict = Depends(get_current_user)) -> dict:
    """Project balance week-by-week over the next N weeks (default 12)."""
    if weeks < 1 or weeks > 520:
        raise HTTPException(status_code=400, detail="weeks must be between 1 and 520.")
    state = _get_state(current_user["id"])
    timeline = [
        {"week": w, "balance": round(state.project_balance(w), 2)}
        for w in range(1, weeks + 1)
    ]
    return {
        "weeks": weeks,
        "starting_balance": state.current_balance(),
        "net_weekly_flow": round(state.net_weekly_flow(), 2),
        "timeline": timeline,
    }


# ── Schedule analytics ────────────────────────────────────────────────────────

@app.get("/api/analytics/income")
@limiter.limit("60/minute")
def analytics_income(request: Request, current_user: dict = Depends(get_current_user)) -> dict:
    events = db.get_events(user_id=current_user["id"])
    groups = sa.income_by_job(events)
    return {
        key: {
            "name": g.name, "rate": g.rate, "total_hours": g.total_hours,
            "total_income": g.total_income, "avg_rate": g.avg_rate,
            "shift_count": len(g.shifts),
        }
        for key, g in groups.items()
    }


@app.get("/api/analytics/efficiency")
@limiter.limit("60/minute")
def analytics_efficiency(request: Request, current_user: dict = Depends(get_current_user)) -> list[dict]:
    events = db.get_events(user_id=current_user["id"])
    report = sa.job_efficiency_report(events)
    return [
        {
            "name": j.name, "total_hours": j.total_hours,
            "total_income": j.total_income, "income_per_hour": j.income_per_hour,
            "early_starts": j.early_starts, "late_ends": j.late_ends,
            "efficiency_note": j.efficiency_note,
        }
        for j in report
    ]


# ── Simulation ────────────────────────────────────────────────────────────────

@app.post("/api/simulate/monte-carlo")
@limiter.limit("10/minute")
def simulate_monte_carlo(request: Request, req: MonteCarloRequest, current_user: dict = Depends(get_current_user)) -> dict:
    state = _get_state(current_user["id"])
    result = run_monte_carlo(state, weeks=req.weeks, n=req.n)
    result.pop("ending_balances", None)  # large array — omit from default JSON response
    return result


@app.post("/api/simulate/whatif")
@limiter.limit("20/minute")
def simulate_what_if(request: Request, req: WhatIfRequest, current_user: dict = Depends(get_current_user)) -> dict:
    state = _get_state(current_user["id"])
    return simulate_whatif(state, req.description, req.dollar_change, req.weeks)


# ── Shifts (CRUD) ─────────────────────────────────────────────────────────────

@app.get("/api/shifts", response_model=list[ShiftOut])
@limiter.limit("60/minute")
def list_shifts(
    request: Request,
    day: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
) -> list[ShiftOut]:
    """Return all shifts for the current user. Optional ?day= filter (e.g. Monday)."""
    if day and day not in _VALID_DAYS:
        raise HTTPException(status_code=400, detail=f"day must be one of {sorted(_VALID_DAYS)}")
    events = db.get_events(day=day, user_id=current_user["id"])
    return [
        ShiftOut(
            id=e.id, title=e.title, category=e.category, day=e.day,
            start_time=e.start_time, end_time=e.end_time,
            hourly_rate=e.hourly_rate, notes=e.notes, shift_date=e.shift_date,
        )
        for e in events
    ]


@app.post("/api/shifts", response_model=ShiftOut, status_code=201)
@limiter.limit("30/minute")
def create_shift(
    request: Request,
    shift_in: ShiftIn,
    current_user: dict = Depends(get_current_user),
) -> ShiftOut:
    """Create a new shift for the current user."""
    from schedule_event import ScheduleEvent
    event = ScheduleEvent(
        title=shift_in.title, category=shift_in.category, day=shift_in.day,
        start_time=shift_in.start_time, end_time=shift_in.end_time,
        hourly_rate=shift_in.hourly_rate, notes=shift_in.notes,
        shift_date=shift_in.shift_date,
    )
    ok, msg = event.validate()
    if not ok:
        raise HTTPException(status_code=422, detail=msg)
    new_id = db.add_event(event, user_id=current_user["id"])
    return ShiftOut(
        id=new_id, title=event.title, category=event.category, day=event.day,
        start_time=event.start_time, end_time=event.end_time,
        hourly_rate=event.hourly_rate, notes=event.notes, shift_date=event.shift_date,
    )


@app.put("/api/shifts/{shift_id}", response_model=ShiftOut)
@limiter.limit("30/minute")
def update_shift(
    request: Request,
    shift_id: int,
    shift_in: ShiftIn,
    current_user: dict = Depends(get_current_user),
) -> ShiftOut:
    """Update a shift. Returns 404 if the shift doesn't exist or belongs to another user."""
    existing = db.get_event_by_id(shift_id, user_id=current_user["id"])
    if existing is None:
        raise HTTPException(status_code=404, detail="Shift not found.")
    from schedule_event import ScheduleEvent
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


@app.delete("/api/shifts/{shift_id}", status_code=204)
@limiter.limit("30/minute")
def delete_shift(
    request: Request,
    shift_id: int,
    current_user: dict = Depends(get_current_user),
) -> None:
    """Delete a shift. Returns 404 if it doesn't exist or belongs to another user."""
    existing = db.get_event_by_id(shift_id, user_id=current_user["id"])
    if existing is None:
        raise HTTPException(status_code=404, detail="Shift not found.")
    db.delete_event_by_id(shift_id)


# ── Optimizer ─────────────────────────────────────────────────────────────────

@app.post("/api/optimize/shifts")
@limiter.limit("20/minute")
def optimize_shifts(request: Request, req: OptimizeRequest, current_user: dict = Depends(get_current_user)) -> dict:
    events = db.get_events(user_id=current_user["id"])
    candidates = candidates_from_events(events)
    result = optimize_shift_selection(candidates, max_hours=req.max_hours)
    return {
        "selected": [
            {"job_name": c.job_name, "hours": c.hours,
             "hourly_rate": c.hourly_rate, "income": c.income}
            for c in result.selected
        ],
        "total_hours": result.total_hours,
        "total_income": result.total_income,
        "hours_budget": result.hours_budget,
        "hours_unused": result.hours_unused,
        "effective_rate": result.effective_rate,
    }


# ── Thin frontend (static files) ──────────────────────────────────────────────

_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    @app.get("/")
    def root() -> FileResponse:
        return FileResponse(os.path.join(_STATIC_DIR, "index.html"))
