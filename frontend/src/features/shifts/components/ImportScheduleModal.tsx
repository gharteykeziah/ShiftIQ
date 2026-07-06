"use client";

import { ChangeEvent, useMemo, useState } from "react";
import { Upload, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { ShiftCategory } from "@/lib/types";
import { parseScheduleCsv, type ParsedShift } from "@/lib/scheduleImport";
import { formatTime12h } from "@/lib/utils";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";

interface ImportScheduleModalProps {
  open: boolean;
  onClose: () => void;
  token: string | null;
  onImported: () => void;
}

type Step = "upload" | "rates" | "review" | "importing";

// Deliberately not the shared lib/utils.ts hoursBetween(): this one keeps 2
// decimal places instead of 1, since it's summed across every shift in an
// imported schedule (potentially dozens) before being multiplied by a rate —
// the coarser 1-decimal rounding used for on-screen display elsewhere would
// compound into a visibly wrong total income here.
function hoursBetween(start: string, end: string): number {
  const [sh, sm] = start.split(":").map(Number);
  const [eh, em] = end.split(":").map(Number);
  return Math.round((eh * 60 + em - (sh * 60 + sm)) / 60 * 100) / 100;
}

/**
 * Import schedule from a CSV export of a weekly-grid spreadsheet (Google
 * Sheets: File > Download > Comma Separated Values). Frontend-only — bulk
 * imports by calling the existing single-shift create endpoint once per
 * parsed shift, so no backend/API changes are needed.
 */
export function ImportScheduleModal({ open, onClose, token, onImported }: ImportScheduleModalProps) {
  const [step, setStep] = useState<Step>("upload");
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [fileName, setFileName] = useState<string | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);

  const [shifts, setShifts] = useState<ParsedShift[]>([]);
  const [excluded, setExcluded] = useState<Set<number>>(new Set());
  const [jobCodes, setJobCodes] = useState<string[]>([]);
  const [rates, setRates] = useState<Record<string, string>>({});
  const [titles, setTitles] = useState<Record<string, string>>({});
  const [category, setCategory] = useState<ShiftCategory>("Work");

  const [importProgress, setImportProgress] = useState(0);
  const [importError, setImportError] = useState<string | null>(null);

  function reset() {
    setStep("upload");
    setFileName(null);
    setParseError(null);
    setShifts([]);
    setExcluded(new Set());
    setJobCodes([]);
    setRates({});
    setTitles({});
    setImportProgress(0);
    setImportError(null);
  }

  function handleClose() {
    reset();
    onClose();
  }

  function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setParseError(null);
    setFileName(file.name);

    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result ?? "");
      const yearNum = Number(year) || new Date().getFullYear();
      const result = parseScheduleCsv(text, yearNum);
      if (result.shifts.length === 0) {
        setParseError(
          "We couldn't find any shifts in that file. Make sure it's a CSV export with a time column (like \"8:00-9:00\") and a row of day names (Monday, Tuesday...) above each week."
        );
        return;
      }
      setShifts(result.shifts);
      setJobCodes(result.jobCodes);
      const initialRates: Record<string, string> = {};
      const initialTitles: Record<string, string> = {};
      for (const code of result.jobCodes) {
        initialRates[code] = "";
        initialTitles[code] = code;
      }
      setRates(initialRates);
      setTitles(initialTitles);
      setStep("rates");
    };
    reader.onerror = () => setParseError("Couldn't read that file. Please try again.");
    reader.readAsText(file);
  }

  function handleContinueToReview() {
    setStep("review");
  }

  const includedShifts = useMemo(
    () => shifts.map((s, i) => ({ ...s, index: i })).filter((s) => !excluded.has(s.index)),
    [shifts, excluded]
  );

  const totals = useMemo(() => {
    let hours = 0;
    let income = 0;
    for (const s of includedShifts) {
      const h = hoursBetween(s.start_time, s.end_time);
      const rate = Number(rates[s.jobCode]) || 0;
      hours += h;
      income += h * rate;
    }
    return { hours: Math.round(hours * 100) / 100, income: Math.round(income * 100) / 100 };
  }, [includedShifts, rates]);

  async function handleImport() {
    if (!token) return;
    setStep("importing");
    setImportError(null);
    setImportProgress(0);

    let failCount = 0;
    for (let i = 0; i < includedShifts.length; i++) {
      const s = includedShifts[i];
      const rate = Number(rates[s.jobCode]) || 0;
      try {
        await api.shifts.create(token, {
          title: titles[s.jobCode]?.trim() || s.jobCode,
          category,
          day: s.day,
          start_time: s.start_time,
          end_time: s.end_time,
          hourly_rate: rate,
          notes: "",
          shift_date: s.date ?? undefined,
        });
      } catch {
        failCount++;
      }
      setImportProgress(i + 1);
    }

    if (failCount > 0) {
      setImportError(`${failCount} shift${failCount === 1 ? "" : "s"} couldn't be saved. The rest were imported.`);
    }
    onImported();
  }

  return (
    <Modal open={open} onClose={handleClose} title="Import schedule">
      {step === "upload" && (
        <div className="space-y-4">
          <p className="text-sm text-muted">
            Export your schedule from Google Sheets as a CSV (File → Download → Comma Separated Values), then upload
            it here. This works for a weekly grid — a time column down the side and a day per column, with one
            block per week.
          </p>
          <Input
            label="Schedule year"
            type="number"
            value={year}
            onChange={(e) => setYear(e.target.value)}
            hint={'Used for dates like "June 1" that don\'t include a year.'}
          />
          <div>
            <label className="mb-1.5 block text-sm font-medium text-text">CSV file</label>
            <label className="flex cursor-pointer items-center justify-center gap-2 rounded-2xl border border-dashed border-border bg-white px-4 py-8 text-sm text-muted hover:bg-surface-hover">
              <Upload className="h-4 w-4" aria-hidden="true" />
              {fileName ?? "Choose a .csv file"}
              <input type="file" accept=".csv,text/csv" className="hidden" onChange={handleFile} />
            </label>
          </div>
          {parseError && <p className="text-sm text-danger">{parseError}</p>}
          <div className="flex justify-end">
            <Button type="button" variant="ghost" onClick={handleClose}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      {step === "rates" && (
        <div className="space-y-4">
          <p className="text-sm text-muted">
            Found {jobCodes.length} job label{jobCodes.length === 1 ? "" : "s"} on your schedule. Set an hourly rate
            (and title, if you want something friendlier than the raw label) for each.
          </p>
          <Select label="Category (applies to all)" value={category} onChange={(e) => setCategory(e.target.value as ShiftCategory)}>
            {(["Work", "Class", "Study", "Meeting", "Personal", "Other"] as ShiftCategory[]).map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
          <div className="max-h-[45vh] space-y-4 overflow-y-auto pr-1">
            {jobCodes.map((code) => (
              <div key={code} className="grid grid-cols-2 gap-3 rounded-lg border border-border p-4">
                <Input
                  label="Title"
                  value={titles[code] ?? code}
                  onChange={(e) => setTitles((t) => ({ ...t, [code]: e.target.value }))}
                  hint={`Sheet label: "${code}"`}
                />
                <Input
                  label="Hourly rate ($)"
                  type="number"
                  min="0"
                  step="0.01"
                  value={rates[code] ?? ""}
                  onChange={(e) => setRates((r) => ({ ...r, [code]: e.target.value }))}
                />
              </div>
            ))}
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setStep("upload")}>
              Back
            </Button>
            <Button type="button" onClick={handleContinueToReview}>
              Continue
            </Button>
          </div>
        </div>
      )}

      {step === "review" && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3 rounded-lg border border-border bg-surface-hover p-4 text-sm">
            <div>
              <p className="text-muted">Shifts</p>
              <p className="font-semibold text-text">{includedShifts.length}</p>
            </div>
            <div>
              <p className="text-muted">Total hours</p>
              <p className="font-semibold text-text">{totals.hours}</p>
            </div>
            <div>
              <p className="text-muted">Estimated income</p>
              <p className="font-semibold text-accent">${totals.income.toFixed(2)}</p>
            </div>
          </div>

          <div className="max-h-[40vh] space-y-2 overflow-y-auto pr-1">
            {shifts.map((s, i) => {
              const isExcluded = excluded.has(i);
              return (
                <div
                  key={i}
                  className={`flex items-center justify-between gap-3 rounded-lg border border-border p-3 text-sm ${
                    isExcluded ? "opacity-40" : ""
                  }`}
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium text-text">
                      {titles[s.jobCode] || s.jobCode} &middot; {s.day}
                      {s.date ? ` (${s.date})` : ""}
                    </p>
                    <p className="text-muted">
                      {formatTime12h(s.start_time)} &ndash; {formatTime12h(s.end_time)}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      setExcluded((prev) => {
                        const next = new Set(prev);
                        if (next.has(i)) next.delete(i);
                        else next.add(i);
                        return next;
                      })
                    }
                    className="shrink-0 text-muted hover:text-danger"
                    aria-label={isExcluded ? "Include this shift" : "Exclude this shift"}
                  >
                    <X className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              );
            })}
          </div>

          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setStep("rates")}>
              Back
            </Button>
            <Button type="button" onClick={handleImport} disabled={includedShifts.length === 0}>
              Import {includedShifts.length} shift{includedShifts.length === 1 ? "" : "s"}
            </Button>
          </div>
        </div>
      )}

      {step === "importing" && (
        <div className="space-y-4 py-6 text-center">
          <p className="text-sm text-muted">
            Importing {importProgress} / {includedShifts.length}...
          </p>
          <div className="h-2 w-full overflow-hidden rounded-full bg-surface-hover">
            <div
              className="h-full rounded-full bg-accent transition-all duration-200"
              style={{ width: `${includedShifts.length ? (importProgress / includedShifts.length) * 100 : 0}%` }}
            />
          </div>
          {importProgress === includedShifts.length && (
            <>
              {importError && <p className="text-sm text-danger">{importError}</p>}
              <Button type="button" onClick={handleClose}>
                Done
              </Button>
            </>
          )}
        </div>
      )}
    </Modal>
  );
}
