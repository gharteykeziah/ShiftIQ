"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Plus, Pencil, Trash2, CalendarClock, Sparkles } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api, ApiError } from "@/lib/api";
import type { ShiftOut, ShiftCategory, Day, OptimizeResult } from "@/lib/types";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { cn } from "@/lib/utils";

const DAYS: Day[] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const CATEGORIES: ShiftCategory[] = ["Work", "Class", "Study", "Meeting", "Personal", "Other"];

// Mirrors CATEGORY_COLORS in schedule_event.py, for visual consistency
// with the desktop app's category color-coding.
const CATEGORY_COLORS: Record<string, string> = {
  Work: "#1B6B3A",
  Class: "#2563EB",
  Study: "#D97706",
  Meeting: "#7C3AED",
  Personal: "#0891B2",
  Other: "#6B7280",
};

function formatTime12h(time: string): string {
  const [hStr, mStr] = time.split(":");
  const h = Number(hStr);
  const m = Number(mStr);
  const ampm = h < 12 ? "AM" : "PM";
  const h12 = h % 12 || 12;
  return `${h12}:${String(m).padStart(2, "0")} ${ampm}`;
}

interface ShiftFormState {
  originalId: number | null; // null = creating a new shift
  title: string;
  category: ShiftCategory;
  day: Day;
  start_time: string;
  end_time: string;
  hourly_rate: string;
  shift_date: string;
  notes: string;
}

function emptyForm(): ShiftFormState {
  return {
    originalId: null,
    title: "",
    category: "Work",
    day: "Monday",
    start_time: "09:00",
    end_time: "17:00",
    hourly_rate: "",
    shift_date: "",
    notes: "",
  };
}

export default function ShiftsPage() {
  const { token } = useAuth();
  const { showToast } = useToast();

  const [shifts, setShifts] = useState<ShiftOut[] | null>(null);
  const [dayFilter, setDayFilter] = useState<Day | "All">("All");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<ShiftFormState>(emptyForm());
  const [formError, setFormError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<ShiftOut | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const [optimizeOpen, setOptimizeOpen] = useState(false);
  const [maxHours, setMaxHours] = useState("20");
  const [optimizeResult, setOptimizeResult] = useState<OptimizeResult | null>(null);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [optimizeError, setOptimizeError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.shifts.list(token, dayFilter === "All" ? undefined : dayFilter);
      setShifts(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong loading your shifts.");
    } finally {
      setIsLoading(false);
    }
  }, [token, dayFilter]);

  useEffect(() => {
    load();
  }, [load]);

  function openAddForm() {
    setForm(emptyForm());
    setFormError(null);
    setFormOpen(true);
  }

  function openEditForm(shift: ShiftOut) {
    setForm({
      originalId: shift.id,
      title: shift.title,
      category: shift.category,
      day: shift.day as Day,
      start_time: shift.start_time,
      end_time: shift.end_time,
      hourly_rate: String(shift.hourly_rate),
      shift_date: shift.shift_date,
      notes: shift.notes,
    });
    setFormError(null);
    setFormOpen(true);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!token) return;

    const title = form.title.trim();
    if (!title) {
      setFormError("Title is required.");
      return;
    }
    if (form.start_time === form.end_time) {
      setFormError("Start and end time can't be the same.");
      return;
    }
    const hourlyRate = form.hourly_rate ? Number(form.hourly_rate) : 0;
    if (Number.isNaN(hourlyRate) || hourlyRate < 0) {
      setFormError("Hourly rate must be $0 or more.");
      return;
    }

    setIsSaving(true);
    setFormError(null);
    try {
      const payload = {
        title,
        category: form.category,
        day: form.day,
        start_time: form.start_time,
        end_time: form.end_time,
        hourly_rate: hourlyRate,
        notes: form.notes,
        shift_date: form.shift_date,
      };
      if (form.originalId !== null) {
        await api.shifts.update(token, form.originalId, payload);
        showToast(`"${title}" updated.`, "success");
      } else {
        await api.shifts.create(token, payload);
        showToast(`"${title}" added.`, "success");
      }
      setFormOpen(false);
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Couldn't save this shift.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete() {
    if (!token || !deleteTarget) return;
    setIsDeleting(true);
    try {
      await api.shifts.delete(token, deleteTarget.id);
      showToast(`"${deleteTarget.title}" removed.`, "info");
      setDeleteTarget(null);
      await load();
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : "Couldn't remove this shift.", "warning");
    } finally {
      setIsDeleting(false);
    }
  }

  function openOptimizeModal() {
    setOptimizeResult(null);
    setOptimizeError(null);
    setOptimizeOpen(true);
  }

  async function handleOptimize(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    const hours = Number(maxHours);
    if (Number.isNaN(hours) || hours <= 0) {
      setOptimizeError("Enter available hours greater than 0.");
      return;
    }
    setIsOptimizing(true);
    setOptimizeError(null);
    try {
      const result = await api.optimize.shifts(token, hours);
      setOptimizeResult(result);
    } catch (err) {
      setOptimizeError(err instanceof ApiError ? err.message : "Couldn't run the optimizer.");
    } finally {
      setIsOptimizing(false);
    }
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl space-y-4 p-6 sm:p-10">
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
            <CardTitle>Couldn&apos;t load your shifts</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <Button onClick={load}>Try again</Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto min-w-0 max-w-4xl space-y-6 p-6 sm:p-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-text">Shifts</h1>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={openOptimizeModal}>
            <Sparkles className="h-4 w-4" aria-hidden="true" />
            Optimize
          </Button>
          <Button size="sm" onClick={openAddForm}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            Add shift
          </Button>
        </div>
      </div>

      <div className="flex min-w-0 gap-2 overflow-x-auto pb-1">
        {(["All", ...DAYS] as const).map((d) => (
          <button
            key={d}
            onClick={() => setDayFilter(d)}
            className={cn(
              "shrink-0 rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors duration-150",
              dayFilter === d ? "bg-text text-white" : "bg-surface text-muted hover:bg-surface-hover"
            )}
          >
            {d}
          </button>
        ))}
      </div>

      {shifts && shifts.length === 0 ? (
        <Card className="flex flex-col items-center gap-3 py-12 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent-light">
            <CalendarClock className="h-6 w-6 text-accent" aria-hidden="true" />
          </span>
          <div>
            <p className="font-semibold text-text">No shifts here yet</p>
            <p className="mt-1 text-sm text-muted">
              {dayFilter === "All" ? "Add your first shift to start planning." : `Nothing scheduled for ${dayFilter}.`}
            </p>
          </div>
          <Button size="sm" onClick={openAddForm}>
            Add shift
          </Button>
        </Card>
      ) : (
        <div className="space-y-3">
          {shifts?.map((shift) => (
            <Card key={shift.id} className="flex items-center justify-between gap-4 p-5">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <p className="truncate font-semibold text-text">{shift.title}</p>
                  <span
                    className="shrink-0 rounded-full px-2 py-0.5 text-xs font-medium text-white"
                    style={{ backgroundColor: CATEGORY_COLORS[shift.category] ?? CATEGORY_COLORS.Other }}
                  >
                    {shift.category}
                  </span>
                </div>
                <p className="mt-0.5 text-sm text-muted">
                  {shift.day} &middot; {formatTime12h(shift.start_time)} &ndash; {formatTime12h(shift.end_time)}
                  {shift.category === "Work" && shift.hourly_rate > 0 && (
                    <> &middot; ${shift.hourly_rate.toFixed(2)}/hr</>
                  )}
                </p>
                {shift.notes && <p className="mt-1 truncate text-sm text-muted">{shift.notes}</p>}
              </div>
              <div className="flex shrink-0 items-center gap-4">
                <button
                  onClick={() => openEditForm(shift)}
                  className="text-muted hover:text-text"
                  aria-label={`Edit ${shift.title}`}
                >
                  <Pencil className="h-4 w-4" aria-hidden="true" />
                </button>
                <button
                  onClick={() => setDeleteTarget(shift)}
                  className="text-muted hover:text-danger"
                  aria-label={`Delete ${shift.title}`}
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Add / Edit modal */}
      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={form.originalId !== null ? "Edit shift" : "Add shift"}
      >
        <form onSubmit={handleSubmit} className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
          <Input
            label="Title"
            value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            required
          />

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-text">Category</label>
              <select
                value={form.category}
                onChange={(e) => setForm((f) => ({ ...f, category: e.target.value as ShiftCategory }))}
                className="w-full rounded-2xl border-0 bg-bg px-4 py-3 text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/40"
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-text">Day</label>
              <select
                value={form.day}
                onChange={(e) => setForm((f) => ({ ...f, day: e.target.value as Day }))}
                className="w-full rounded-2xl border-0 bg-bg px-4 py-3 text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/40"
              >
                {DAYS.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Start time"
              type="time"
              value={form.start_time}
              onChange={(e) => setForm((f) => ({ ...f, start_time: e.target.value }))}
              required
            />
            <Input
              label="End time"
              type="time"
              value={form.end_time}
              onChange={(e) => setForm((f) => ({ ...f, end_time: e.target.value }))}
              hint="Earlier than start time = overnight shift, that's fine."
              required
            />
          </div>

          <Input
            label="Hourly rate ($)"
            type="number"
            min="0"
            step="0.01"
            value={form.hourly_rate}
            onChange={(e) => setForm((f) => ({ ...f, hourly_rate: e.target.value }))}
            hint="Only used for income calculations when category is Work."
          />

          <Input
            label="Specific date (optional)"
            type="date"
            value={form.shift_date}
            onChange={(e) => setForm((f) => ({ ...f, shift_date: e.target.value }))}
            hint="Leave blank for a recurring weekly shift with no fixed date."
          />

          <Input
            label="Notes (optional)"
            value={form.notes}
            onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
          />

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

      {/* Delete confirmation */}
      <Modal open={!!deleteTarget} onClose={() => setDeleteTarget(null)} title="Delete this shift?">
        <p className="mb-4 text-sm text-muted">
          Remove &quot;{deleteTarget?.title}&quot;? This can&apos;t be undone.
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

      {/* Optimizer */}
      <Modal open={optimizeOpen} onClose={() => setOptimizeOpen(false)} title="Optimize shifts">
        <form onSubmit={handleOptimize} className="space-y-4">
          <Input
            label="Hours available this week"
            type="number"
            min="0.5"
            step="0.5"
            value={maxHours}
            onChange={(e) => setMaxHours(e.target.value)}
            hint="We'll pick the combination of your logged shifts that maximizes income within this budget."
            required
          />
          {optimizeError && <p className="text-sm text-danger">{optimizeError}</p>}
          <Button type="submit" className="w-full" isLoading={isOptimizing}>
            Run optimizer
          </Button>
        </form>

        {optimizeResult && (
          <div className="mt-5 space-y-3 border-t border-border/60 pt-4">
            {optimizeResult.selected.length === 0 ? (
              <p className="text-sm text-muted">No work shifts with an hourly rate were found to optimize.</p>
            ) : (
              <div className="space-y-2">
                {optimizeResult.selected.map((c, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span className="text-text">
                      {c.job_name} &middot; {c.hours}h &middot; ${c.hourly_rate.toFixed(2)}/hr
                    </span>
                    <span className="font-semibold text-accent">${c.income.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            )}
            <div className="grid grid-cols-2 gap-3 border-t border-border/60 pt-3 text-sm">
              <div>
                <p className="text-muted">Total hours</p>
                <p className="font-semibold text-text">
                  {optimizeResult.total_hours} / {optimizeResult.hours_budget}
                </p>
              </div>
              <div>
                <p className="text-muted">Total income</p>
                <p className="font-semibold text-accent">${optimizeResult.total_income.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-muted">Hours unused</p>
                <p className="font-semibold text-text">{optimizeResult.hours_unused}</p>
              </div>
              <div>
                <p className="text-muted">Effective rate</p>
                <p className="font-semibold text-text">${optimizeResult.effective_rate.toFixed(2)}/hr</p>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
