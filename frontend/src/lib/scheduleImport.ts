import type { Day } from "./types";

// Parses a CSV export of a weekly-grid work schedule — the common format
// for campus job spreadsheets: a "Time" column of ranges like "8:00-9:00"
// down the left side, and one column per weekday across the top, with
// multiple week-blocks stacked vertically (each starting with its own row
// of day names). This is intentionally scoped to CSV only — real tabular
// data the browser can parse reliably — rather than photos/PDFs of a
// schedule, which look different for every user and can't be parsed
// consistently without a server-side OCR/AI step.

export interface ParsedShift {
  day: Day;
  /** ISO yyyy-mm-dd if a date row could be matched under the day header, else null (recurring weekly). */
  date: string | null;
  start_time: string;
  end_time: string;
  /** The raw label found in the cell — e.g. "LIB", "OIP", "Ambassador". */
  jobCode: string;
}

export interface ParsedSchedule {
  shifts: ParsedShift[];
  jobCodes: string[];
}

const DAY_NAMES: Day[] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

const MONTHS: Record<string, number> = {
  january: 1, jan: 1,
  february: 2, feb: 2,
  march: 3, mar: 3,
  april: 4, apr: 4,
  may: 5,
  june: 6, jun: 6,
  july: 7, jul: 7,
  august: 8, aug: 8,
  september: 9, sep: 9, sept: 9,
  october: 10, oct: 10,
  november: 11, nov: 11,
  december: 12, dec: 12,
};

/** Minimal RFC4180-ish CSV parser — handles quoted fields containing commas/newlines. */
export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        field += c;
      }
    } else if (c === '"') {
      inQuotes = true;
    } else if (c === ",") {
      row.push(field);
      field = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      field = "";
      rows.push(row);
      row = [];
    } else {
      field += c;
    }
  }
  if (field.length > 0 || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

function matchDay(cell: string): Day | null {
  const clean = cell.trim().toUpperCase();
  return DAY_NAMES.find((d) => d.toUpperCase() === clean) ?? null;
}

function isTimeRangeLabel(cell: string): boolean {
  return /^\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}$/.test(cell.trim());
}

function parseDateCell(cell: string, year: number): string | null {
  const m = cell.trim().match(/^([A-Za-z]+)\.?\s+(\d{1,2})$/);
  if (!m) return null;
  const month = MONTHS[m[1].toLowerCase()];
  if (!month) return null;
  const day = Number(m[2]);
  if (day < 1 || day > 31) return null;
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

/**
 * Converts one side of a "8:00-9:00" style label to 24h "HH:MM", assuming
 * a single continuous work day (e.g. 8 AM-5 PM). `isPM` is shared state
 * threaded through an entire week-block's time rows in order: once a "12"
 * is seen the schedule has crossed into the afternoon, so any hour 1-7
 * seen afterward is treated as PM. This matches ordinary business-hours
 * schedules; overnight or irregular formats should be fixed up after import.
 */
function to24h(part: string, isPM: { value: boolean }): string {
  const [hStr, mStr = "00"] = part.split(":");
  let h = Number(hStr);
  const m = Number(mStr);
  if (h === 12) {
    isPM.value = true;
  } else if (isPM.value && h >= 1 && h <= 7) {
    h += 12;
  }
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function parseTimeRange(label: string, isPM: { value: boolean }): { start: string; end: string } {
  const [a, b] = label.split("-").map((s) => s.trim());
  const start = to24h(a, isPM);
  const end = to24h(b, isPM);
  return { start, end };
}

export function parseScheduleCsv(text: string, year: number): ParsedSchedule {
  const rows = parseCsv(text);
  const shifts: ParsedShift[] = [];
  const jobCodesSet = new Set<string>();

  let currentDayCols: { day: Day; col: number }[] = [];
  let currentDateCols: Record<number, string> = {};
  let pendingDateRow = false;
  const isPM = { value: false };

  for (const row of rows) {
    const dayMatches = row.map((cell, idx) => ({ idx, day: matchDay(cell) })).filter((x) => x.day);

    if (dayMatches.length >= 2) {
      currentDayCols = dayMatches.map((x) => ({ day: x.day as Day, col: x.idx }));
      currentDateCols = {};
      isPM.value = false;
      pendingDateRow = true;
      continue;
    }

    if (pendingDateRow) {
      currentDateCols = {};
      for (const { col } of currentDayCols) {
        const iso = parseDateCell(row[col] ?? "", year);
        if (iso) currentDateCols[col] = iso;
      }
      pendingDateRow = false;
      continue;
    }

    // Real-world sheets like this usually only spell out weekday names
    // (Monday/Tuesday...) once, at the very top. Every week after that is
    // just a "Time" row carrying new dates, reusing the same column
    // positions established by that first header — so a fresh week block
    // is recognized by column A literally reading "Time", not by another
    // day-name row.
    const firstCell = (row[0] ?? "").trim().toLowerCase();
    if (firstCell === "time" && currentDayCols.length > 0) {
      currentDateCols = {};
      for (const { col } of currentDayCols) {
        const iso = parseDateCell(row[col] ?? "", year);
        if (iso) currentDateCols[col] = iso;
      }
      isPM.value = false; // each new week's time column restarts at morning
      continue;
    }

    const timeLabel = (row[0] ?? "").trim();
    if (!timeLabel || !isTimeRangeLabel(timeLabel) || currentDayCols.length === 0) continue;

    const { start, end } = parseTimeRange(timeLabel, isPM);
    for (const { day, col } of currentDayCols) {
      const code = (row[col] ?? "").trim();
      if (!code) continue;
      jobCodesSet.add(code);
      shifts.push({ day, date: currentDateCols[col] ?? null, start_time: start, end_time: end, jobCode: code });
    }
  }

  return { shifts, jobCodes: Array.from(jobCodesSet).sort() };
}
