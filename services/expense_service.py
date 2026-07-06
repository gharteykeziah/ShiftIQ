"""
services/expense_service.py — CRUD business logic for expenses.

Moved verbatim out of api.py's list_expenses()/add_expense()/update_expense()/delete_expense().
"""
from __future__ import annotations

from fastapi import HTTPException

import database as db
from dependencies import get_state
from model import Expense
from schemas import ExpenseOut


def _to_out(expense: Expense) -> ExpenseOut:
    return ExpenseOut(
        name=expense.name, amount=expense.amount, category=expense.category,
        date=expense.date, frequency=expense.frequency,
        weekly_amount=round(expense.weekly_amount(), 2),
    )


def list_expenses(user_id: int) -> list[ExpenseOut]:
    return [_to_out(e) for e in db.load_expenses(user_id=user_id)]


def add_expense(user_id: int, name: str, amount: float, category: str, date: str, frequency: str) -> ExpenseOut:
    state = get_state(user_id)
    expense = Expense(name, amount, category, date, frequency)
    ok, message = state.add_expense(expense)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return _to_out(expense)


def update_expense(
    user_id: int, name: str, new_name: str, amount: float, category: str, date: str, frequency: str,
) -> ExpenseOut:
    """If renaming (new_name != name), checks that the new name is not already
    taken BEFORE deleting the old record, preventing silent data loss."""
    state = get_state(user_id)
    if new_name != name and any(e.name == new_name for e in state.expenses):
        raise HTTPException(status_code=400, detail=f"An expense named '{new_name}' already exists.")
    ok, message = state.delete_expense(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Expense '{name}' not found.")
    expense = Expense(new_name, amount, category, date, frequency)
    ok, message = state.add_expense(expense)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return _to_out(expense)


def delete_expense(user_id: int, name: str) -> dict:
    state = get_state(user_id)
    ok, message = state.delete_expense(name)
    if not ok:
        raise HTTPException(status_code=404, detail=message)
    return {"message": message}
