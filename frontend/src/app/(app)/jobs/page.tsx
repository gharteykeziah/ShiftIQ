"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Plus, Pencil, Trash2, Briefcase } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api, ApiError } from "@/lib/api";
import type { JobOut, Frequency } from "@/lib/types";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";

const FREQUENCIES: Frequency[] = ["Daily", "Weekly", "Biweekly", "Monthly"];

interface JobFormState {
  originalName: string | null; // null = creating a new job
  name: string;
  amount: string;
  frequency: Frequency;
}

const EMPTY_FORM: JobFormState = { originalName: null, name: "", amount: "", frequency: "Weekly" };

export default function JobsPage() {
  const { token } = useAuth();
  const { showToast } = useToast();

  const [jobs, setJobs] = useState<JobOut[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<JobFormState>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<JobOut | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.jobs.list(token);
      setJobs(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong loading your jobs.");
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  function openAddForm() {
    setForm(EMPTY_FORM);
    setFormError(null);
    setFormOpen(true);
  }

  function openEditForm(job: JobOut) {
    setForm({ originalName: job.name, name: job.name, amount: String(job.amount), frequency: job.frequency });
    setFormError(null);
    setFormOpen(true);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!token) return;

    const name = form.name.trim();
    const amount = Number(form.amount);
    if (!name) {
      setFormError("Job name is required.");
      return;
    }
    if (Number.isNaN(amount) || amount <= 0) {
      setFormError("Enter an amount greater than $0.");
      return;
    }

    setIsSaving(true);
    setFormError(null);
    try {
      if (form.originalName) {
        await api.jobs.update(token, form.originalName, { name, amount, frequency: form.frequency });
        showToast(`"${name}" updated.`, "success");
      } else {
        await api.jobs.create(token, { name, amount, frequency: form.frequency });
        showToast(`"${name}" added.`, "success");
      }
      setFormOpen(false);
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Couldn't save this job.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete() {
    if (!token || !deleteTarget) return;
    setIsDeleting(true);
    try {
      await api.jobs.delete(token, deleteTarget.name);
      showToast(`"${deleteTarget.name}" removed.`, "info");
      setDeleteTarget(null);
      await load();
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : "Couldn't remove this job.", "warning");
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
            <CardTitle>Couldn&apos;t load your jobs</CardTitle>
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
        <h1 className="text-2xl font-bold text-text">Jobs</h1>
        <Button size="sm" onClick={openAddForm}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          Add job
        </Button>
      </div>

      {jobs && jobs.length === 0 ? (
        <Card className="flex flex-col items-center gap-3 py-12 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent-light">
            <Briefcase className="h-6 w-6 text-accent" aria-hidden="true" />
          </span>
          <div>
            <p className="font-semibold text-text">No jobs yet</p>
            <p className="mt-1 text-sm text-muted">Add your first job to start tracking income.</p>
          </div>
          <Button size="sm" onClick={openAddForm}>
            Add job
          </Button>
        </Card>
      ) : (
        <div className="space-y-3">
          {jobs?.map((job) => (
            <Card key={job.name} className="flex items-center justify-between gap-4 p-5">
              <div className="min-w-0">
                <p className="truncate font-semibold text-text">{job.name}</p>
                <p className="mt-0.5 text-sm text-muted">
                  ${job.amount.toFixed(2)} &middot; {job.frequency}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-4">
                <p className="text-sm font-semibold text-accent">${job.weekly_income.toFixed(2)}/wk</p>
                <button
                  onClick={() => openEditForm(job)}
                  className="text-muted hover:text-text"
                  aria-label={`Edit ${job.name}`}
                >
                  <Pencil className="h-4 w-4" aria-hidden="true" />
                </button>
                <button
                  onClick={() => setDeleteTarget(job)}
                  className="text-muted hover:text-danger"
                  aria-label={`Delete ${job.name}`}
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal open={formOpen} onClose={() => setFormOpen(false)} title={form.originalName ? "Edit job" : "Add job"}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Job name"
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            required
          />
          <Input
            label="Amount ($)"
            type="number"
            min="0.01"
            step="0.01"
            value={form.amount}
            onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
            hint="Total pay per period below, not an hourly rate — e.g. $450 for Weekly means $450/week total."
            required
          />
          <div>
            <label className="mb-1.5 block text-sm font-medium text-text">Frequency</label>
            <select
              value={form.frequency}
              onChange={(e) => setForm((f) => ({ ...f, frequency: e.target.value as Frequency }))}
              className="w-full rounded-2xl border-0 bg-bg px-4 py-3 text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/40"
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

      <Modal open={!!deleteTarget} onClose={() => setDeleteTarget(null)} title="Delete this job?">
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
