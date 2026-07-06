"""
schemas.py — All Pydantic request/response models for the ShiftIQ API.

Kept in one module rather than split per router: these are pure data
contracts with no business logic, and splitting them further would add
import surface across routers without reducing any real coupling.

Moved verbatim out of api.py — no validation rule changed.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from config import MONTE_CARLO_RUNS
from validation import strip_html, VALID_CATEGORIES, VALID_DAYS, VALID_FREQUENCIES


# ── Jobs ──────────────────────────────────────────────────────────────────────

class JobIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0, le=1_000_000)
    frequency: str = "Weekly"

    @field_validator("name", mode="before")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        v = strip_html(str(v))
        if not v:
            raise ValueError("name cannot be empty")
        return v

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        if v not in VALID_FREQUENCIES:
            raise ValueError(f"frequency must be one of {sorted(VALID_FREQUENCIES)}")
        return v


class JobOut(BaseModel):
    name: str
    amount: float
    frequency: str
    weekly_income: float


# ── Expenses ──────────────────────────────────────────────────────────────────

class ExpenseIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0, le=1_000_000)
    category: str = Field(min_length=1, max_length=50)
    date: str
    frequency: str = "Monthly"

    @field_validator("name", "category", mode="before")
    @classmethod
    def sanitize_strings(cls, v: str) -> str:
        v = strip_html(str(v))
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
        if v not in VALID_FREQUENCIES:
            raise ValueError(f"frequency must be one of {sorted(VALID_FREQUENCIES)}")
        return v


class ExpenseOut(BaseModel):
    name: str
    amount: float
    category: str
    date: str
    frequency: str
    weekly_amount: float


# ── State / balance ───────────────────────────────────────────────────────────

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


# ── Simulation ────────────────────────────────────────────────────────────────

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
        v = strip_html(str(v))
        if not v:
            raise ValueError("description cannot be empty")
        return v


# ── Optimizer ─────────────────────────────────────────────────────────────────

class OptimizeRequest(BaseModel):
    max_hours: float = Field(gt=0, le=168)


# ── Auth ──────────────────────────────────────────────────────────────────────

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


# ── Shifts ────────────────────────────────────────────────────────────────────

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
        v = strip_html(str(v))
        if not v:
            raise ValueError("title cannot be empty")
        return v

    @field_validator("notes", mode="before")
    @classmethod
    def sanitize_notes(cls, v: str) -> str:
        return strip_html(str(v))

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(f"category must be one of {sorted(VALID_CATEGORIES)}")
        return v

    @field_validator("day")
    @classmethod
    def validate_day(cls, v: str) -> str:
        if v not in VALID_DAYS:
            raise ValueError(f"day must be one of {sorted(VALID_DAYS)}")
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
