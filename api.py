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

from fastapi import FastAPI, HTTPException, Request
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
from config import MONTE_CARLO_RUNS

# ── Rate limiter ──────────────────────────────────────────────────────────────
# Keys requests by IP address. Limits:
#   - Auth endpoints: 10/minute  (slow down password-guessing attacks)
#   - Write endpoints: 30/minute (prevent bulk data abuse)
#   - Read endpoints:  60/minute (comfortable for real users, not for scrapers)
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(
    title="ShiftIQ API",
    description="Schedule-driven financial simulation engine, exposed over HTTP.",
    version="1.3.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Allow the React dev server (port 3000) and any deployed frontend to call the API.
# In production, replace "*" with your actual frontend domain for tighter security.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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


def _get_state() -> FinancialState:
    """Fresh FinancialState per request — sqlite is the single source of
    truth, so there is no in-memory state to keep consistent across requests."""
    return FinancialState()


# ── Input sanitization helper ─────────────────────────────────────────────────

_HTML_TAG_RE = re.compile(r'<[^>]+>')

def _strip_html(value: str) -> str:
    """Remove all HTML/script tags from a string and strip surrounding whitespace.

    This is the first line of defence against XSS: anything a user types that
    contains <script>, <img onerror=...>, or any other tag is stripped before
    it ever reaches the database or gets echoed back in a response.
    """
    return _HTML_TAG_RE.sub('', value).strip()


_VALID_FREQUENCIES = {"Weekly", "Bi-Weekly", "Monthly", "Annually", "One-Time"}


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


# ── Financial state ───────────────────────────────────────────────────────────

@app.get("/api/state", response_model=StateSummary)
@limiter.limit("60/minute")
def get_state_summary(request: Request) -> StateSummary:
    state = _get_state()
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
def update_balance(request: Request, body: BalanceIn) -> dict:
    """Update the current saved balance."""
    state = _get_state()
    ok, message = state.set_balance(body.amount)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"balance": body.amount, "message": message}


# ── Jobs ──────────────────────────────────────────────────────────────────────

@app.get("/api/jobs", response_model=list[JobOut])
@limiter.limit("60/minute")
def list_jobs(request: Request) -> list[JobOut]:
    return [
        JobOut(name=j.name, amount=j.amount, frequency=j.frequency,
               weekly_income=round(j.weekly_income(), 2))
        for j in db.load_jobs()
    ]


@app.post("/api/jobs", response_model=JobOut, status_code=201)
@limiter.limit("30/minute")
def add_job(request: Request, job_in: JobIn) -> JobOut:
    state = _get_state()
    job = Job(job_in.name, job_in.amount, job_in.frequency)
    ok, message = state.add_job(job)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return JobOut(name=job.name, amount=job.amount, frequency=job.frequency,
                  weekly_income=round(job.weekly_income(), 2))


@app.put("/api/jobs/{name}", response_model=JobOut)
@limiter.limit("30/minute")
def update_job(request: Request, name: str, job_in: JobIn) -> JobOut:
    """Update an existing job's amount and/or frequency by name."""
    state = _get_state()
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
def delete_job(request: Request, name: str) -> dict:
    state = _get_state()
    ok, message = state.delete_job(name)
    if not ok:
        raise HTTPException(status_code=404, detail=message)
    return {"message": message}


# ── Expenses ──────────────────────────────────────────────────────────────────

@app.get("/api/expenses", response_model=list[ExpenseOut])
@limiter.limit("60/minute")
def list_expenses(request: Request) -> list[ExpenseOut]:
    return [
        ExpenseOut(name=e.name, amount=e.amount, category=e.category,
                   date=e.date, frequency=e.frequency,
                   weekly_amount=round(e.weekly_amount(), 2))
        for e in db.load_expenses()
    ]


@app.post("/api/expenses", response_model=ExpenseOut, status_code=201)
@limiter.limit("30/minute")
def add_expense(request: Request, expense_in: ExpenseIn) -> ExpenseOut:
    state = _get_state()
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
def update_expense(request: Request, name: str, expense_in: ExpenseIn) -> ExpenseOut:
    """Update an existing expense by name."""
    state = _get_state()
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
def delete_expense(request: Request, name: str) -> dict:
    state = _get_state()
    ok, message = state.delete_expense(name)
    if not ok:
        raise HTTPException(status_code=404, detail=message)
    return {"message": message}


# ── History ───────────────────────────────────────────────────────────────────

@app.get("/api/history")
@limiter.limit("60/minute")
def get_history(request: Request) -> dict:
    """Return all daily financial snapshots ordered by date ascending."""
    snapshots = db.load_history()
    return {
        "count": len(snapshots),
        "snapshots": snapshots,
    }


# ── Insights ──────────────────────────────────────────────────────────────────

@app.get("/api/insights")
@limiter.limit("60/minute")
def get_insights(request: Request) -> dict:
    """Return plain-English financial insights generated by the InsightEngine."""
    state = _get_state()
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
def get_projection(request: Request, weeks: int = 12) -> dict:
    """Project balance week-by-week over the next N weeks (default 12)."""
    if weeks < 1 or weeks > 520:
        raise HTTPException(status_code=400, detail="weeks must be between 1 and 520.")
    state = _get_state()
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
def analytics_income(request: Request) -> dict:
    events = db.get_events()
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
def analytics_efficiency(request: Request) -> list[dict]:
    events = db.get_events()
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
def simulate_monte_carlo(request: Request, req: MonteCarloRequest) -> dict:
    state = _get_state()
    result = run_monte_carlo(state, weeks=req.weeks, n=req.n)
    result.pop("ending_balances", None)  # large array — omit from default JSON response
    return result


@app.post("/api/simulate/whatif")
@limiter.limit("20/minute")
def simulate_what_if(request: Request, req: WhatIfRequest) -> dict:
    state = _get_state()
    return simulate_whatif(state, req.description, req.dollar_change, req.weeks)


# ── Optimizer ─────────────────────────────────────────────────────────────────

@app.post("/api/optimize/shifts")
@limiter.limit("20/minute")
def optimize_shifts(request: Request, req: OptimizeRequest) -> dict:
    events = db.get_events()
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
