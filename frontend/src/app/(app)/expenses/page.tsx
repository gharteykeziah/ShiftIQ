"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Plus, Pencil, Trash2, Receipt } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api, ApiError } from "@/lib/api";
import type { ExpenseOut, Frequency } from "@/lib/types";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";

const FREQUENCIES: Frequency[] = ["Daily", "Weekly", "Biweekly", "Monthly"];

interface ExpenseFormState {
  originalName: string | null; // null = creating a new expense
  name: string;
  amount: string;
  category: string;
  date: string;
  frequency: Frequency;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function emptyForm(): ExpenseFormState {
  return { originalName: null, name: "", amount: "", category: "", date: todayIso(), frequency: "Monthly" };
}

export default function ExpensesPage() {
  const { token } = useAuth();
  const { showToast } = useToast();

  const [expenses, setExpenses] = useState<ExpenseOut[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<ExpenseFormState>(emptyForm());
  const [formError, setFormError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<ExpenseOut | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.expenses.list(token);
      setExpenses(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong loading your expenses.");
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  function openAddForm() {
    setForm(emptyForm());
    setFormError(null);
    setFormOpen(true);
  }

  function openEditForm(expense: ExpenseOut) {
    setForm({
      originalName: expense.name,
      name: expense.name,
      amount: String(expense.amount),
      category: expense.category,
      date: expense.date,
      frequency: expense.frequency,
    });
    setFormError(null);
    setFormOpen(true);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!token) return;

    const name = form.name.trim();
    const category = form.category.trim();
    const amount = Number(form.amount);
    if (!name) {
      setFormError("Expense name is required.");
      return;
    }
    if (!category) {
      setFormError("Category is required.");
      return;
    }
    if (!form.date) {
      setFormError("Date is required.");
      return;
    }
    if (Number.isNaN(amount) || amount <= 0) {
      setFormError("Enter an amount greater than $0.");
      return;
    }

    setIsSaving(true);
    setFormError(null);
    try {
      const payload = { name, amount, category, date: form.date, frequency: form.frequency };
      if (form.originalName) {
        await api.expenses.update(token, form.originalName, payload);
        showToast(`"${name}" updated.`, "success");
      } else {
        await api.expenses.create(token, payload);
        showToast(`"${name}" added.`, "success");
      }
      setFormOpen(false);
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Couldn't save this expense.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete() {
    if (!token || !deleteTarget) return;
    setIsDeleting(true);
    try {
      await api.expenses.delete(token, deleteTarget.name);
      showToast(`"${deleteTarget.name}" removed.`, "info");
      setDeleteTarget(null);
      await load();
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : "Couldn't remove this expense.", "warning");
    } finally {
      setIsDeleting(false);
    }
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl space-y-4 p-6 sm:p-10">
        <Skeleton className="h-8 w-32" />
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-lg p-6 sm:p-10">
        <Card>
          <CardHeader>
            <CardTitle>Couldn&apos;t load your expenses</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <Button onClick={load}>Try again</Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6 sm:p-10">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text">Expenses</h1>
        <Button size="sm" onClick={openAddForm}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          Add expense
        </Button>
      </div>

      {expenses && expenses.length === 0 ? (
        <Card className="flex flex-col items-center gap-3 py-12 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent-light">
            <Receipt className="h-6 w-6 text-accent" aria-hidden="true" />
          </span>
          <div>
            <p className="font-semibold text-text">No expenses yet</p>
            <p className="mt-1 text-sm text-muted">Add your first expense to start tracking spending.</p>
          </div>
          <Button size="sm" onClick={openAddForm}>
            Add expense
          </Button>
        </Card>
      ) : (
        <div className="space-y-3">
          {expenses?.map((expense) => (
            <Card key={expense.name} className="flex items-center justify-between gap-4 p-5">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <p className="truncate font-semibold text-text">{expense.name}</p>
                  <span className="shrink-0 rounded-full bg-accent-light px-2 py-0.5 text-xs font-medium text-accent">
                    {expense.category}
                  </span>
                </div>
                <p className="mt-0.5 text-sm text-muted">
                  ${expense.amount.toFixed(2)} &middot; {expense.frequency} &middot; {expense.date}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-4">
                <p className="text-sm font-semibold text-danger">${expense.weekly_amount.toFixed(2)}/wk</p>
                <button
                  onClick={() => openEditForm(expense)}
                  className="text-muted hover:text-text"
                  aria-label={`Edit ${expense.name}`}
                >
                  <Pencil className="h-4 w-4" aria-hidden="true" />
                </button>
                <button
                  onClick={() => setDeleteTarget(expense)}
                  className="text-muted hover:text-danger"
                  aria-label={`Delete ${expense.name}`}
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={form.originalName ? "Edit expense" : "Add expense"}
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Expense name"
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            required
          />
          <Input
            label="Category"
            placeholder="Food, Rent, Transport, ..."
            value={form.category}
            onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
            required
          />
          <Input
            label="Amount ($)"
            type="number"
            min="0.01"
            step="0.01"
            value={form.amount}
            onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
            hint="Total cost per period below, not a daily average."
            required
          />
          <Input
            label="Date"
            type="date"
            value={form.date}
            onChange={(e) => setForm((f) => ({ ...f, date: e.target.value }))}
            required
          />
          <div>
            <label className="mb-1.5 block text-sm font-medium text-text">Frequency</label>
            <select
              value={form.frequency}
              onChange={(e) => setForm((f) => ({ ...f, frequency: e.target.value as Frequency }))}
              className="w-full rounded-2xl border border-border bg-white px-4 py-3 text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/40"
            >
              {FREQUENCIES.map((freq) => (
                <option key={freq} value={freq}>
                  {freq}
                </option>
              ))}
            </select>
          </div>
          {formError && <p className="text-sm text-danger">{formError}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setFormOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" isLoading={isSaving}>
              Save
            </Button>
          </div>
        </form>
      </Modal>

      <Modal open={!!deleteTarget} onClose={() => setDeleteTarget(null)} title="Delete this expense?">
        <p className="mb-4 text-sm text-muted">
          Remove &quot;{deleteTarget?.name}&quot;? This can&apos;t be undone.
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setDeleteTarget(null)}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handleDelete} isLoading={isDeleting}>
            Delete
          </Button>
        </div>
      </Modal>
    </div>
  );
}
