"""
date_parser.py — Flexible date-aware schedule import parser for FRE.

Three modes are auto-detected from the first meaningful line of the input:

  DAILY   — all shifts share one specific date
    Date: 2026-06-18
    Admissions: 9-12
    Library: 14-17

  WEEKLY  — shifts mapped from day-names to a selected calendar week
    Admissions: Mon 9-12 Wed 14-17 Fri 10-13
    Cashier: Tue 17-21
    — OR with an explicit week anchor —
    Week: 2026-06-15
    Admissions: Mon 9-12

  MONTHLY — each job line carries explicit ISO dates
    Month: 2026-06
    Admissions: 2026-06-01 9-12 2026-06-03 2-5
    Library: 2026-06-07 1-4 2026-06-14 1-4

Returns a DateParseResult whose .shifts list contains DatedShift objects,
each with a concrete ISO date, day name, 24-hour start/end, and job name.

Public API
──────────
    parse_schedule(text, week_start=None) → DateParseResult
"""

from __future__ import annotations

import re
import datetime
import calendar
from typing import NamedTuple


# ── Output types ──────────────────────────────────────────────────────────────

class DatedShift(NamedTuple):
    """One parsed shift with a concrete calendar date attached."""
    job_name:   str   # normalised title-case
    date:       str   # "YYYY-MM-DD"
    day:        str   # "Monday" … "Sunday"
    start_time: str   # "HH:MM" 24-hour
    end_time:   str   # "HH:MM" 24-hour
    rate:       float = 0.0  # hourly rate if specified inline, else 0


class DateParseResult:
    """Returned by parse_schedule()."""
    __slots__ = ("mode", "shifts", "errors", "warnings", "anchor")

    def __init__(self, mode: str = "weekly") -> None:
        self.mode:     str              = mode    # "daily" | "weekly" | "monthly"
        self.shifts:   list[DatedShift] = []
        self.errors:   list[str]        = []
        self.warnings: list[str]        = []
        self.anchor:   str              = ""      # detected date / week / month string


# ── Month-name lookup table ───────────────────────────────────────────────────

_MONTH_IDX: dict[str, int] = {}
for _i, _mn in enumerate(calendar.month_name):
    if _mn:
        _MONTH_IDX[_mn.lower()]      = _i   # "january" → 1
        _MONTH_IDX[_mn[:3].lower()]  = _i   # "jan" → 1

def _parse_natural_date(text: str) -> datetime.date | None:
    """
    Parse natural-language dates like:
      "Thursday, June 18"
      "Thursday, June 18, 2026"
      "June 18"
      "June 18, 2026"
    Returns a datetime.date or None.
    """
    text = text.strip().rstrip(".,")
    # Strip leading weekday
    text = re.sub(r"^(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday),?\s*",
                  "", text, flags=re.IGNORECASE)
    m = re.match(r"^(\w+)\s+(\d{1,2})(?:,?\s*(\d{4}))?$", text.strip())
    if not m:
        return None
    month_str, day_str, year_str = m.groups()
    month = _MONTH_IDX.get(month_str.lower())
    if not month:
        return None
    year = int(year_str) if year_str else datetime.date.today().year
    try:
        return datetime.date(year, month, int(day_str))
    except ValueError:
        return None


# ── Day-name lookup table ─────────────────────────────────────────────────────

_FULL_DAYS = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]

_DAY_IDX: dict[str, int] = {}
for _i, _d in enumerate(_FULL_DAYS):
    _DAY_IDX[_d.lower()]     = _i   # full name
    _DAY_IDX[_d[:3].lower()] = _i   # 3-letter abbrev
for _abbr, _idx in [("tues", 1), ("weds", 2), ("thur", 3), ("thurs", 3)]:
    _DAY_IDX[_abbr] = _idx


def _day_name(d: datetime.date) -> str:
    return _FULL_DAYS[d.weekday()]


def _resolve_day_idx(token: str) -> "int | None":
    return _DAY_IDX.get(token.strip().lower())


def _day_to_date(day_token: str, week_start: datetime.date) -> "datetime.date | None":
    idx = _resolve_day_idx(day_token)
    if idx is None:
        return None
    return week_start + datetime.timedelta(days=idx)


# ── Time helpers ──────────────────────────────────────────────────────────────

def _norm_hour(raw: str) -> int:
    """
    Convert a bare-hour string to a 24-hour integer.
    1-7 → PM (+12), 8-12 → AM/noon (keep), 13+ → already 24h.
    """
    h = int(raw)
    if h > 12:
        return h
    if h == 0:
        return 0
    if h <= 7:
        return h + 12
    return h


_AMPM_RE = re.compile(r"^(\d{1,2}(?::\d{2})?)\s*([AaPp][Mm])$")


def _parse_time_tok(raw: str) -> str:
    """
    Parse a time token → 'HH:MM' (24-hour).
    Handles: '9', '9:30', '14', '9:00 AM', '1:00 PM', '9AM', '9 pm'.
    """
    raw = raw.strip()
    m = _AMPM_RE.match(raw)
    if m:
        time_part, ampm = m.groups()
        if ":" in time_part:
            hs, ms = time_part.split(":", 1)
            h, mn = int(hs), int(ms)
        else:
            h, mn = int(time_part), 0
        if ampm.lower() == "pm" and h != 12:
            h += 12
        elif ampm.lower() == "am" and h == 12:
            h = 0
        if h > 23 or mn > 59:
            raise ValueError(f"Invalid time: {raw!r}")
        return f"{h:02d}:{mn:02d}"
    # No AM/PM — use heuristic (1-7 → PM)
    if ":" in raw:
        hs, ms = raw.split(":", 1)
        h, mn = _norm_hour(hs), int(ms)
    else:
        h, mn = _norm_hour(raw), 0
    if h > 23 or mn > 59:
        raise ValueError(f"Invalid time: {raw!r}")
    return f"{h:02d}:{mn:02d}"


def _has_ampm(raw: str) -> bool:
    return bool(_AMPM_RE.match(raw.strip()))


def _parse_pair(rs: str, re_s: str) -> tuple[str, str]:
    """
    Parse a start–end pair, handling AM/PM and overnight shifts.
    If explicit AM/PM is present, trust it. Otherwise apply heuristic.
    """
    start = _parse_time_tok(rs)
    if _has_ampm(re_s):
        end = _parse_time_tok(re_s)
    else:
        sh  = int(start.split(":")[0])
        reh_raw = re_s.strip().split(":")[0]
        reh = int(reh_raw) if reh_raw.isdigit() else 0
        if sh >= 17 and 1 <= reh <= 7:
            if ":" in re_s:
                eh, em = re_s.split(":", 1)
                end = f"{int(eh):02d}:{int(em):02d}"
            else:
                end = f"{reh:02d}:00"
        else:
            end = _parse_time_tok(re_s)
    return start, end


# ── Regexes ───────────────────────────────────────────────────────────────────

_TIME_P   = r"\d{1,2}(?::\d{2})?(?:\s*[AaPp][Mm])?"
_RANGE_RE = re.compile(rf"({_TIME_P})\s*[-–]\s*({_TIME_P})")

# Inline rate: "@ $12.50"  "@ 12.50"  "@ $12/hr"  "@12.50"
_RATE_RE  = re.compile(r"@\s*\$?(\d+(?:\.\d+)?)\s*(?:/hr?)?", re.IGNORECASE)

def _extract_rate(line: str) -> tuple[str, float]:
    """Strip inline rate annotation from a line. Returns (clean_line, rate)."""
    m = _RATE_RE.search(line)
    if m:
        return line[:m.start()].rstrip() + line[m.end():], float(m.group(1))
    return line, 0.0

_DAY_ALTS = (
    "monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    "mon|tue|tues|wed|weds|thu|thur|thurs|fri|sat|sun"
)
_DAY_RE = re.compile(rf"\b({_DAY_ALTS})\b", re.IGNORECASE)

_ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

# Header patterns (first line)
_DATE_HDR_RE  = re.compile(r"^date\s*:?\s*(\d{4}-\d{2}-\d{2})\s*$", re.IGNORECASE)
_WEEK_HDR_RE  = re.compile(r"^week\s*:?\s*(\d{4}-\d{2}-\d{2})\s*$", re.IGNORECASE)
_MONTH_HDR_RE = re.compile(r"^month\s*:?\s*(\d{4}-\d{2})\s*$", re.IGNORECASE)

# "Job name: rest of line"  OR  "Job name — rest of line" (em dash)
_JOB_COLON_RE  = re.compile(r"^([^:]+):\s*(.+)$")
_JOB_EMDASH_RE = re.compile(r"^([^—]+?)\s*—\s*(.+)$")


# ── Mode detection ────────────────────────────────────────────────────────────

def _detect_mode(lines: list[str]) -> tuple[str, str, list[str]]:
    """
    Scan for a mode header in the first non-empty line.
    Returns (mode, anchor_string, body_lines).
    """
    for i, raw in enumerate(lines):
        line = raw.split("#")[0].strip()
        if not line:
            continue
        m = _DATE_HDR_RE.match(line)
        if m:
            return "daily", m.group(1), lines[i + 1:]
        m = _WEEK_HDR_RE.match(line)
        if m:
            return "weekly", m.group(1), lines[i + 1:]
        m = _MONTH_HDR_RE.match(line)
        if m:
            return "monthly", m.group(1), lines[i + 1:]
        # Natural language date: "Thursday, June 18" or "June 18, 2026"
        nat = _parse_natural_date(line)
        if nat:
            return "daily", nat.isoformat(), lines[i + 1:]
        # No recognized header — default to weekly
        return "weekly", "", lines[i:]
    return "weekly", "", []


# ── Per-mode parsers ──────────────────────────────────────────────────────────

def _parse_daily(
    lines:  list[str],
    anchor: str,
    result: DateParseResult,
) -> None:
    """
    Daily mode: one date header, then job lines.
    Each line: "JobName: HH-HH"  or  "JobName HH-HH"
    """
    try:
        target = datetime.date.fromisoformat(anchor)
    except ValueError:
        result.errors.append(f"Invalid date in header: {anchor!r}")
        return

    day_name = _day_name(target)
    date_str = target.isoformat()

    for raw in lines:
        line = raw.split("#")[0].strip()
        if not line:
            continue

        # Strip inline rate before any other parsing ("@ $12.50")
        line, inline_rate = _extract_rate(line)
        line = line.strip()

        # Try em dash first (avoids splitting on colon inside time like "9:00")
        m = (_JOB_EMDASH_RE.match(line) if "—" in line else None) or _JOB_COLON_RE.match(line)
        if m:
            job_raw, rest = m.group(1).strip(), m.group(2).strip()
        else:
            rm = _RANGE_RE.search(line)
            if not rm:
                result.warnings.append(f"Could not parse: {line!r}")
                continue
            job_raw = line[:rm.start()].strip()
            rest    = line[rm.start():]

        if not job_raw:
            result.warnings.append(f"Missing job name in: {line!r}")
            continue

        ranges = _RANGE_RE.findall(rest)
        if not ranges:
            result.warnings.append(f"No time range for {job_raw!r}: {rest!r}")
            continue

        for rs, re_s in ranges:
            try:
                start, end = _parse_pair(rs, re_s)
                result.shifts.append(DatedShift(
                    job_name=job_raw.title(),
                    date=date_str,
                    day=day_name,
                    start_time=start,
                    end_time=end,
                    rate=inline_rate,
                ))
            except ValueError as exc:
                result.errors.append(f"{job_raw}: {exc}")


def _parse_weekly(
    lines:      list[str],
    anchor:     str,
    week_start: datetime.date,
    result:     DateParseResult,
) -> None:
    """
    Weekly mode: shift day-names are mapped to a specific calendar week.

    Handles all three sub-formats:
      • "Job: Day HH-HH Day HH-HH"   (colon, most common)
      • "Day Job HH-HH"               (day-first, no colon)
      • "Job Day HH-HH"               (job-first, no colon)
    """
    # Override week_start if an explicit anchor was found in the text
    if anchor:
        try:
            ws = datetime.date.fromisoformat(anchor)
            week_start = ws - datetime.timedelta(days=ws.weekday())
        except ValueError:
            result.warnings.append(f"Ignoring unrecognised week date: {anchor!r}")

    for raw in lines:
        line = raw.split("#")[0].strip()
        if not line:
            continue

        # ── 1. Colon format "Job: Day HH-HH ..." ────────────────────────────
        m = _JOB_COLON_RE.match(line)
        if m:
            job_raw, rest = m.group(1).strip(), m.group(2).strip()
            _extract_weekly_pairs(job_raw, rest, week_start, result)
            continue

        # ── 2. Day-first format "Thu Cashier 12-9" ──────────────────────────
        day_m = _DAY_RE.match(line)
        if day_m:
            day_tok = day_m.group(1)
            rest    = line[day_m.end():].strip()
            rm = _RANGE_RE.search(rest)
            if rm:
                job_part = rest[:rm.start()].strip()
                if not job_part:
                    result.warnings.append(f"Missing job name in: {line!r}")
                    continue
                actual = _day_to_date(day_tok, week_start)
                if actual is None:
                    result.warnings.append(f"Unrecognised day {day_tok!r} in: {line!r}")
                    continue
                try:
                    start, end = _parse_pair(rm.group(1), rm.group(2))
                    result.shifts.append(DatedShift(
                        job_name=job_part.title(),
                        date=actual.isoformat(),
                        day=_day_name(actual),
                        start_time=start,
                        end_time=end,
                    ))
                except ValueError as exc:
                    result.errors.append(f"{job_part}: {exc}")
                continue

        # ── 3. Job-first, no colon "Cashier Wed 12-9" ───────────────────────
        inner_day = _DAY_RE.search(line)
        if inner_day:
            job_raw = line[:inner_day.start()].strip()
            rest    = line[inner_day.start():]
            if job_raw:
                _extract_weekly_pairs(job_raw, rest, week_start, result)
                continue

        result.warnings.append(f"Could not parse: {line!r}")


def _extract_weekly_pairs(
    job_raw:    str,
    rest:       str,
    week_start: datetime.date,
    result:     DateParseResult,
) -> None:
    """
    From `rest`, scan for "Day HH-HH" pairs and append DatedShift objects.
    Used by _parse_weekly for colon and job-first formats.
    """
    pos       = 0
    found_any = False

    while pos < len(rest):
        dm = _DAY_RE.search(rest, pos)
        if not dm:
            break
        rm = _RANGE_RE.search(rest, dm.end())
        if not rm:
            break

        day_tok = dm.group(1)
        actual  = _day_to_date(day_tok, week_start)
        if actual:
            try:
                start, end = _parse_pair(rm.group(1), rm.group(2))
                result.shifts.append(DatedShift(
                    job_name=job_raw.title(),
                    date=actual.isoformat(),
                    day=_day_name(actual),
                    start_time=start,
                    end_time=end,
                ))
                found_any = True
            except ValueError as exc:
                result.errors.append(f"{job_raw}: {exc}")

        pos = rm.end()

    if not found_any:
        result.warnings.append(f"No valid day+time found for {job_raw!r}")


def _parse_monthly(
    lines:  list[str],
    anchor: str,
    result: DateParseResult,
) -> None:
    """
    Monthly mode: each job line contains explicit ISO dates.
    Format: "JobName: YYYY-MM-DD HH-HH YYYY-MM-DD HH-HH ..."
    """
    for raw in lines:
        line = raw.split("#")[0].strip()
        if not line:
            continue

        # Extract job name
        m = _JOB_COLON_RE.match(line)
        if m:
            job_raw, rest = m.group(1).strip(), m.group(2).strip()
        else:
            iso_m = _ISO_DATE_RE.search(line)
            if iso_m:
                job_raw = line[:iso_m.start()].strip()
                rest    = line[iso_m.start():]
            else:
                result.warnings.append(f"No ISO date in: {line!r}")
                continue

        if not job_raw:
            result.warnings.append(f"Missing job name in: {line!r}")
            continue

        # Scan tokens for YYYY-MM-DD HH-HH pairs
        tokens    = rest.split()
        i         = 0
        found_any = False

        while i < len(tokens):
            if _ISO_DATE_RE.fullmatch(tokens[i]):
                date_str = tokens[i]
                i += 1
                # The time range may span 1-3 tokens: "9-12" or "9" "-" "12"
                chunk = " ".join(tokens[i:i + 3])
                rm = _RANGE_RE.search(chunk)
                if rm:
                    try:
                        d = datetime.date.fromisoformat(date_str)
                        start, end = _parse_pair(rm.group(1), rm.group(2))
                        result.shifts.append(DatedShift(
                            job_name=job_raw.title(),
                            date=date_str,
                            day=_day_name(d),
                            start_time=start,
                            end_time=end,
                        ))
                        found_any = True
                        # Advance past the tokens consumed by the range
                        tok_count = len(rm.group(0).split())
                        i += max(1, tok_count)
                    except ValueError as exc:
                        result.errors.append(f"{job_raw} on {date_str}: {exc}")
                        i += 1
                else:
                    result.warnings.append(
                        f"{job_raw}: no time range after {date_str!r}"
                    )
                    i += 1
            else:
                i += 1

        if not found_any:
            result.warnings.append(f"No date-time pairs found for {job_raw!r}")


# ── Public API ────────────────────────────────────────────────────────────────

def parse_schedule(
    text:       str,
    week_start: "datetime.date | None" = None,
) -> DateParseResult:
    """
    Parse *text* into DatedShift objects.

    Parameters
    ──────────
    text        Raw schedule text (any of the three supported formats).
    week_start  Used only in weekly mode when the text has no Week: header.
                If None, defaults to the Monday of the current calendar week.

    Returns
    ───────
    DateParseResult with:
      .mode     — "daily" | "weekly" | "monthly"
      .shifts   — list of DatedShift (each with a concrete ISO date)
      .errors   — unrecoverable parse problems
      .warnings — skipped lines or minor issues
      .anchor   — the date/week/month string found in the header (if any)
    """
    if week_start is None:
        today      = datetime.date.today()
        week_start = today - datetime.timedelta(days=today.weekday())

    lines             = text.splitlines()
    mode, anchor, body = _detect_mode(lines)

    result        = DateParseResult(mode=mode)
    result.anchor = anchor

    if mode == "daily":
        _parse_daily(body, anchor, result)
    elif mode == "monthly":
        _parse_monthly(body, anchor, result)
    else:
        _parse_weekly(body, anchor, week_start, result)

    return result
