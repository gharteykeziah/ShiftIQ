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
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import database as db
from financial_state import FinancialState
from insight_engine import InsightEngine
from simulation import run_monte_carlo, simulate_whatif
from optimizer import optimize_shift_selection, candidates_from_events
import shift_analytics as sa
from model import Job, Expense
from config import MONTE_CARLO_RUNS

app = FastAPI(
    title="ShiftIQ API",
    description="Schedule-driven financial simulation engine, exposed over HTTP.",
    version="1.1.0",
)

_insight_engine = InsightEngine()


def _get_state() -> FinancialState:
    """Fresh FinancialState per request — sqlite is the single source of
    truth, so there is no in-memory state to keep consistent across requests."""
    return FinancialState()


# ── Schemas ───────────────────────────────────────────────────────────────────

class JobIn(BaseModel):
    name: str
    amount: float = Field(gt=0)
    frequency: str = "Weekly"


class JobOut(BaseModel):
    name: str
    amount: float
    frequency: str
    weekly_income: float


class ExpenseIn(BaseModel):
    name: str
    amount: float = Field(gt=0)
    category: str
    date: str
    frequency: str = "Monthly"


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


class MonteCarloRequest(BaseModel):
    weeks: int = Field(gt=0, le=520)
    n: int = Field(default=MONTE_CARLO_RUNS, gt=0, le=10_000)


class WhatIfRequest(BaseModel):
    description: str
    dollar_change: float
    weeks: int = Field(gt=0, le=520)


class OptimizeRequest(BaseModel):
    max_hours: float = Field(gt=0, le=168)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# ── Financial state ───────────────────────────────────────────────────────────

@app.get("/api/state", response_model=StateSummary)
def get_state_summary() -> StateSummary:
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


# ── Jobs ──────────────────────────────────────────────────────────────────────

@app.get("/api/jobs", response_model=list[JobOut])
def list_jobs() -> list[JobOut]:
    return [
        JobOut(name=j.name, amount=j.amount, frequency=j.frequency,
               weekly_income=round(j.weekly_income(), 2))
        for j in db.load_jobs()
    ]


@app.post("/api/jobs", response_model=JobOut, status_code=201)
def add_job(job_in: JobIn) -> JobOut:
    state = _get_state()
    job = Job(job_in.name, job_in.amount, job_in.frequency)
    ok, message = state.add_job(job)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return JobOut(name=job.name, amount=job.amount, frequency=job.frequency,
                  weekly_income=round(job.weekly_income(), 2))


@app.delete("/api/jobs/{name}")
def delete_job(name: str) -> dict:
    state = _get_state()
    ok, message = state.delete_job(name)
    if not ok:
        raise HTTPException(status_code=404, detail=message)
    return {"message": message}


# ── Expenses ──────────────────────────────────────────────────────────────────

@app.get("/api/expenses", response_model=list[ExpenseOut])
def list_expenses() -> list[ExpenseOut]:
    return [
        ExpenseOut(name=e.name, amount=e.amount, category=e.category,
                   date=e.date, frequency=e.frequency,
                   weekly_amount=round(e.weekly_amount(), 2))
        for e in db.load_expenses()
    ]


@app.post("/api/expenses", response_model=ExpenseOut, status_code=201)
def add_expense(expense_in: ExpenseIn) -> ExpenseOut:
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


@app.delete("/api/expenses/{name}")
def delete_expense(name: str) -> dict:
    state = _get_state()
    ok, message = state.delete_expense(name)
    if not ok:
        raise HTTPException(status_code=404, detail=message)
    return {"message": message}


# ── Schedule analytics ────────────────────────────────────────────────────────

@app.get("/api/analytics/income")
def analytics_income() -> dict:
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
def analytics_efficiency() -> list[dict]:
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
def simulate_monte_carlo(req: MonteCarloRequest) -> dict:
    state = _get_state()
    result = run_monte_carlo(state, weeks=req.weeks, n=req.n)
    result.pop("ending_balances", None)  # large array — omit from default JSON response
    return result


@app.post("/api/simulate/whatif")
def simulate_what_if(req: WhatIfRequest) -> dict:
    state = _get_state()
    return simulate_whatif(state, req.description, req.dollar_change, req.weeks)


# ── Optimizer ─────────────────────────────────────────────────────────────────

@app.post("/api/optimize/shifts")
def optimize_shifts(req: OptimizeRequest) -> dict:
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
