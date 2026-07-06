"""routers/expenses.py — /api/expenses CRUD."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from dependencies import get_current_user, limiter
from schemas import ExpenseIn, ExpenseOut
from services import expense_service

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


@router.get("", response_model=list[ExpenseOut])
@limiter.limit("60/minute")
def list_expenses(request: Request, current_user: dict = Depends(get_current_user)) -> list[ExpenseOut]:
    return expense_service.list_expenses(current_user["id"])


@router.post("", response_model=ExpenseOut, status_code=201)
@limiter.limit("30/minute")
def add_expense(
    request: Request, expense_in: ExpenseIn, current_user: dict = Depends(get_current_user),
) -> ExpenseOut:
    return expense_service.add_expense(
        current_user["id"], expense_in.name, expense_in.amount,
        expense_in.category, expense_in.date, expense_in.frequency,
    )


@router.put("/{name}", response_model=ExpenseOut)
@limiter.limit("30/minute")
def update_expense(
    request: Request, name: str, expense_in: ExpenseIn, current_user: dict = Depends(get_current_user),
) -> ExpenseOut:
    """Update an existing expense by name."""
    return expense_service.update_expense(
        current_user["id"], name, expense_in.name, expense_in.amount,
        expense_in.category, expense_in.date, expense_in.frequency,
    )


@router.delete("/{name}")
@limiter.limit("30/minute")
def delete_expense(request: Request, name: str, current_user: dict = Depends(get_current_user)) -> dict:
    return expense_service.delete_expense(current_user["id"], name)
