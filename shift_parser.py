"""
shift_parser.py
───────────────
ShiftIQ — Shift Parser & Weekly Schedule Importer

Lets users paste their full weekly schedule as a single text block
instead of entering each shift manually.

INPUT FORMAT
────────────
    JobName: Day Start-End  [Day Start-End ...]

    Admissions: Mon 9-12 Wed 2-5 Fri 10-1
    Library: Tue 1-4 Thu 3-6

    Or spread across multiple lines:
    Admissions:
        Mon 9-12
        Wed 2-5

TIME RULES
──────────
    Hours 1–7   → PM assumed   (1 → 13:00, 5 → 17:00)
    Hours 8–12  → AM / noon    (9 → 09:00, 12 → 12:00)
    With minutes: 9:30-12:30   (always exact)
    Night shifts work too: 22-6 → 22:00–06:00

INTEGRATION
───────────
    Reads job IDs from existing fre_jobs table.
    Inserts into existing fre_shifts table.
    Runs conflict detection before EVERY insert.
    Does NOT touch the database schema.

USAGE
─────
    from shift_parser import import_schedule_text, print_import_result

    result = import_schedule_text(\"\"\"
        Admissions: Mon 9-12 Wed 2-5
        Library: Tue 1-4 Thu 3-6
    \"\"\")
    print_import_result(result)
"""
from __future__ import annotations


import re
from dataclasses import dataclass, field

from schedule_core import (
    _Database,
    Engine,
    Shift,
    ValidationError,
    _DB_PATH,
    _DAYS,
    _DAY_ALIASES,
    _fmt12,
    _duration_min,
)


# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES — plain containers, no logic
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ParsedShift:
    """One shift extracted from the raw text, before database interaction."""
    job_name:   str
    day:        str
    start_time: str   # normalised "HH:MM"
    end_time:   str   # normalised "HH:MM"


@dataclass
class ParseResult:
    """Everything the parser found (or failed to find) in the text block."""
    shifts:   list[ParsedShift] = field(default_factory=list)
    warnings: list[str]         = field(default_factory=list)   # non-fatal
    errors:   list[str]         = field(default_factory=list)   # bad input


@dataclass
class ImportResult:
    """Full outcome after parsing + validating + writing to the database."""
    imported:  list[dict] = field(default_factory=list)   # saved to DB
    skipped:   list[dict] = field(default_factory=list)   # not saved
    conflicts: list[str]  = field(default_factory=list)   # overlap messages
    warnings:  list[str]  = field(default_factory=list)   # parse warnings
    errors:    list[str]  = field(default_factory=list)   # fatal problems


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — TIME NORMALISATION
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_hour(raw: str) -> int:
    """
    Convert a bare-hour string to a 24-hour integer.

    The rule for a student / part-time work context:
      1–7  → assumed PM  (add 12)
      8–12 → assumed AM or noon (keep as-is)
      13+  → already 24-hour (keep as-is)

    Examples
    ────────
      '9'  →  9   (9 AM)
      '12' → 12   (noon)
      '1'  → 13   (1 PM)
      '5'  → 17   (5 PM)
      '22' → 22   (10 PM — night shift)
    """
    h = int(raw)
    if h > 12:
        return h        # already 24-hour style (e.g. 13, 22)
    if h == 0:
        return 0        # midnight
    if h <= 7:
        return h + 12   # 1-7 → afternoon/evening
    return h            # 8-12 → morning / noon


def _parse_time_token(raw: str) -> str:
    """
    Convert a time token ('9', '9:30', '14', '22') to 'HH:MM'.

    Raises ValueError with a readable message if the token is invalid.
    """
    raw = raw.strip()
    if ':' in raw:
        h_str, m_str = raw.split(':', 1)
        h = _normalize_hour(h_str)
        m = int(m_str)
    else:
        h = _normalize_hour(raw)
        m = 0

    if h > 23:
        raise ValueError(f"Hour {h} is out of range (00–23)")
    if m > 59:
        raise ValueError(f"Minutes {m} are out of range (00–59)")

    return f"{h:02d}:{m:02d}"


def _parse_time_pair(raw_start: str, raw_end: str) -> tuple[str, str]:
    """
    Normalise a start–end pair together, handling the overnight edge case.

    Problem: for a night shift like '22-6', the standard _normalize_hour
    would turn '6' into 18:00 (6 PM) because h<=7 triggers the PM rule.
    But here '6' clearly means 6 AM — the morning after.

    Rule: if the start hour (after conversion) is in the evening (≥ 17:00)
    and the raw end is a small number (1–7), treat the end as AM (no +12).

    Examples
    ─────────
      '9',  '12' → ('09:00', '12:00')  — normal day shift
      '2',  '5'  → ('14:00', '17:00')  — afternoon
      '22', '6'  → ('22:00', '06:00')  — night shift ★
      '10', '1'  → ('10:00', '13:00')  — straddles noon
    """
    # Parse start normally
    start_str = _parse_time_token(raw_start)
    start_h   = int(start_str.split(':')[0])

    # For end: extract the raw hour to check the overnight condition
    raw_end_h = int(raw_end.split(':')[0]) if ':' in raw_end else int(raw_end)

    # Night-shift fix: evening start + small raw end → end is AM not PM
    if start_h >= 17 and 1 <= raw_end_h <= 7:
        # Keep end as AM (bypass the +12 PM rule)
        if ':' in raw_end:
            eh_str, em_str = raw_end.split(':', 1)
            end_h = int(eh_str)   # keep as-is (already AM)
            end_m = int(em_str)
        else:
            end_h = raw_end_h
            end_m = 0
        if end_h > 23:
            raise ValueError(f"Hour {end_h} is out of range (00–23)")
        end_str = f"{end_h:02d}:{end_m:02d}"
    else:
        end_str = _parse_time_token(raw_end)

    return start_str, end_str


def _normalize_day(raw: str) -> str | None:
    """
    Map a day name or common abbreviation to the canonical form.

    Returns None (not an exception) if the day is unrecognised —
    the caller decides whether to warn or skip.

    Accepted forms (case-insensitive):
      Mon / Monday / monday, Tue / Tuesday, Wed / Wednesday,
      Thu / Thursday, Fri / Friday, Sat / Saturday, Sun / Sunday
    """
    cleaned = raw.strip()

    # Full-name match
    for d in _DAYS:
        if cleaned.lower() == d.lower():
            return d

    # 3-letter abbreviation (Mon → Monday, etc.)
    return _DAY_ALIASES.get(cleaned.lower())


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — PARSER
# ─────────────────────────────────────────────────────────────────────────────

# ── Regex patterns ────────────────────────────────────────────────────────────

# One shift token: "Mon 9-12" or "Wednesday 9:30-12:00"
# Group names: day, start, end
_SHIFT_TOKEN = re.compile(
    r'(?P<day>'
    r'Mon(?:day)?|Tues(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Weds?|'
    r'Thurs(?:day)?|Thur(?:sday)?|Thu(?:rsday)?|Fri(?:day)?|'
    r'Sat(?:urday)?|Sun(?:day)?'
    r')'
    r'\s+'
    r'(?P<start>\d{1,2}(?::\d{2})?)'
    r'\s*[-–]\s*'
    r'(?P<end>\d{1,2}(?::\d{2})?)',
    re.IGNORECASE,
)

# A job declaration: "Job Name:" optionally followed by shift tokens on the same line.
# Group 1 = job name, Group 2 = rest of line (may contain shifts)
_JOB_DECL = re.compile(r'^([^:\d][^:]*?):\s*(.*)', re.DOTALL)

# Colon-less format: "JobName Day Time-Time"  e.g. "cashier wed 12-9"
# Group 1 = job name prefix (letters/spaces before the day keyword)
_DAY_KW = (r'Mon(?:day)?|Tues(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Weds?|'
           r'Thurs(?:day)?|Thur(?:sday)?|Thu(?:rsday)?|'
           r'Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?')
_INLINE_JOB = re.compile(
    r'^([A-Za-z][A-Za-z\s]*?)\s+(?=' + _DAY_KW + r')',
    re.IGNORECASE,
)

# Day-first format: "Day JobName Time-Time"  e.g. "Mon Admissions 9-12"
# Captures: day, job (word(s) between day and time), start, end
_DAY_JOB_TOKEN = re.compile(
    r'(?P<day>' + _DAY_KW + r')'
    r'\s+'
    r'(?P<job>[A-Za-z][A-Za-z\s]*?)\s+'
    r'(?P<start>\d{1,2}(?::\d{2})?)'
    r'\s*[-–]\s*'
    r'(?P<end>\d{1,2}(?::\d{2})?)',
    re.IGNORECASE,
)


def parse_schedule_text(text: str) -> ParseResult:
    """
    Parse a free-text weekly schedule block into structured shift data.

    The parser is deliberately forgiving:
      - Unknown days       → warning, shift skipped
      - Bad time values    → warning, shift skipped
      - Zero/tiny shifts   → warning, shift skipped
      - No job header      → warning on affected lines
      - Blank lines / #    → silently ignored

    Nothing raises an exception to the caller — all problems go into
    result.warnings or result.errors.

    Parameters
    ──────────
    text : the raw schedule block (multiline string)

    Returns a ParseResult.
    """
    result = ParseResult()

    if not text or not text.strip():
        result.errors.append(
            "Input is empty. "
            "Paste your schedule like:  Admissions: Mon 9-12 Wed 2-5"
        )
        return result

    lines         = text.strip().splitlines()
    current_job   = None   # name of the job we are currently assigning shifts to
    found_any_job = False

    for line_num, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()

        # Skip blank lines and comments
        if not line or line.startswith('#'):
            continue

        # ── Check if this line starts a new job section ───────────────────────
        job_match = _JOB_DECL.match(line)
        if job_match:
            candidate = job_match.group(1).strip()
            remainder = job_match.group(2).strip()

            # Guard: make sure the "job name" is not actually a time or day token.
            # (e.g. the colon in "9:30" should not trigger a job declaration)
            looks_like_time = bool(re.fullmatch(r'\d[\d:]*', candidate))
            looks_like_day  = bool(_normalize_day(candidate))

            if not looks_like_time and not looks_like_day and candidate:
                current_job   = candidate
                found_any_job = True
                # Shifts may appear on the same line as the job name —
                # continue parsing 'remainder' as the active line content
                line = remainder

        # ── Also accept colon-less format: "JobName Day Time-Time" ───────────
        # e.g. "cashier wed 12-9"  or  "Admissions Mon 9-12 Wed 2-5"
        elif _SHIFT_TOKEN.search(line):
            inline = _INLINE_JOB.match(line)
            if inline:
                candidate = inline.group(1).strip()
                looks_like_time = bool(re.fullmatch(r'\d[\d:]*', candidate))
                looks_like_day  = bool(_normalize_day(candidate))
                if candidate and not looks_like_time and not looks_like_day:
                    current_job   = candidate
                    found_any_job = True
                    # leave 'line' unchanged — _SHIFT_TOKEN will find day+time

        # ── Day-first format: "Day JobName Time-Time" on same line ──────────
        # e.g. "Mon Admissions 9-12 Tue admissions 1-4"
        # Each token carries its own job name — parse them independently
        if _DAY_JOB_TOKEN.search(line) and not job_match:
            for m in _DAY_JOB_TOKEN.finditer(line):
                raw_day   = m.group("day")
                raw_job   = m.group("job").strip()
                raw_start = m.group("start")
                raw_end   = m.group("end")

                # Skip if "job" is actually a day name (false positive)
                if _normalize_day(raw_job):
                    continue

                day = _normalize_day(raw_day)
                if day is None:
                    result.warnings.append(
                        f"Line {line_num}: Unrecognised day '{raw_day}' — skipped.")
                    continue

                try:
                    start_time, end_time = _parse_time_pair(raw_start, raw_end)
                except ValueError as e:
                    result.warnings.append(
                        f"Line {line_num}: Invalid time '{raw_start}-{raw_end}' — {e} — skipped.")
                    continue

                dur = _duration_min(start_time, end_time)
                if dur < 15:
                    result.warnings.append(
                        f"Line {line_num}: {day} {raw_start}-{raw_end} — "
                        f"too short ({dur} min) — skipped.")
                    continue

                result.shifts.append(ParsedShift(
                    job_name=raw_job,
                    day=day,
                    start_time=start_time,
                    end_time=end_time,
                ))
                found_any_job = True
            continue   # skip the normal _SHIFT_TOKEN scan for this line

        # ── If no job is active yet, warn and move on ─────────────────────────
        if not current_job:
            if line:
                result.warnings.append(
                    f"Line {line_num}: '{line[:60]}' — no job section active. "
                    "Add a job name before listing shifts  (e.g. 'Admissions: ...')"
                )
            continue

        # ── Extract every shift token from the current line ───────────────────
        tokens_found = False

        for match in _SHIFT_TOKEN.finditer(line):
            tokens_found = True
            raw_day   = match.group("day")
            raw_start = match.group("start")
            raw_end   = match.group("end")

            # Normalise day name
            day = _normalize_day(raw_day)
            if day is None:
                result.warnings.append(
                    f"Line {line_num}: Unrecognised day '{raw_day}' — skipped. "
                    "Use Mon/Tue/Wed/Thu/Fri/Sat/Sun or the full name."
                )
                continue

            # Normalise start and end times (pair-aware for overnight shifts)
            try:
                start_time, end_time = _parse_time_pair(raw_start, raw_end)
            except ValueError as e:
                result.warnings.append(
                    f"Line {line_num}: Invalid time in '{match.group()}' — {e} — skipped."
                )
                continue

            # Check shift has a meaningful duration
            dur = _duration_min(start_time, end_time)
            if dur == 0:
                result.warnings.append(
                    f"Line {line_num}: {day} {raw_start}-{raw_end} — "
                    "start and end are the same time — skipped."
                )
                continue
            if dur < 15:
                result.warnings.append(
                    f"Line {line_num}: {day} {raw_start}-{raw_end} — "
                    f"only {dur} minutes (minimum is 15 min) — skipped."
                )
                continue

            result.shifts.append(ParsedShift(
                job_name=current_job,
                day=day,
                start_time=start_time,
                end_time=end_time,
            ))

        # Warn if a line with digits didn't produce any shift tokens
        # (only when there is a job active, so job-name-only lines stay quiet)
        if not tokens_found and line and re.search(r'\d', line):
            result.warnings.append(
                f"Line {line_num}: Could not read a shift from '{line[:60]}'. "
                "Expected format: 'Mon 9-12' or 'Monday 9:30-12:00'"
            )

    if not found_any_job:
        result.errors.append(
            "No job sections found in the input. "
            "Start each block with 'JobName:' "
            "(e.g. 'Admissions: Mon 9-12 Wed 2-5')."
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — DATABASE IMPORT
# ─────────────────────────────────────────────────────────────────────────────

def import_schedule_text(text: str, db_path: str = _DB_PATH) -> ImportResult:
    """
    Parse a schedule text block, then import valid shifts into the database.

    For each parsed shift the function:
      1. Looks up the job name in fre_jobs  → error if not found
      2. Checks for exact duplicates        → warning + skip if duplicate
      3. Runs conflict detection            → conflict message + skip if clash
         (checks both the existing database AND the other shifts being
          imported in the same batch, so two pasted shifts can't silently
          collide with each other)
      4. Inserts clean shifts into fre_shifts

    The program NEVER crashes regardless of what is pasted.

    Parameters
    ──────────
    text    : raw schedule block (multiline string)
    db_path : path to the SQLite database

    Returns an ImportResult.
    """
    result = ImportResult()

    # ── Step 1: parse the raw text ────────────────────────────────────────────
    parse = parse_schedule_text(text)
    result.warnings.extend(parse.warnings)
    result.errors.extend(parse.errors)

    if not parse.shifts:
        if not result.errors:
            result.errors.append("No valid shifts were found in the input.")
        return result

    # ── Step 2: open database ─────────────────────────────────────────────────
    db = _Database(db_path)

    # Load all shifts already in the database (for conflict + duplicate checks)
    existing: list[Shift] = db.get_shifts()

    # As we successfully import each shift, we add it to this list
    # so the NEXT shift in the same paste can see it during conflict detection.
    committed: list[Shift] = []

    # ── Step 3: process each parsed shift ─────────────────────────────────────
    for ps in parse.shifts:

        # 3a — Look up the job in the database ──────────────────────────────
        job = db.get_job_by_name(ps.job_name)
        if job is None:
            result.errors.append(
                f"Job '{ps.job_name}' was not found in the database. "
                f"Create it first:  Scheduler().add_job('{ps.job_name}', hourly_rate=...)"
            )
            result.skipped.append(_skipped(ps, f"Job '{ps.job_name}' not in database"))
            continue

        # 3b — Duplicate check ───────────────────────────────────────────────
        # Skip if the exact same job + day + times already exist.
        if _is_duplicate(ps, job.id, existing):
            result.warnings.append(
                f"Duplicate skipped: {ps.job_name} — "
                f"{ps.day} {_fmt12(ps.start_time)} – {_fmt12(ps.end_time)}"
            )
            result.skipped.append(_skipped(ps, "Duplicate — already exists"))
            continue

        # 3c — Conflict detection ────────────────────────────────────────────
        # Check against both the current database AND this batch's committed shifts.
        all_for_check = existing + committed
        clashing = Engine.detect_conflicts(
            ps.start_time, ps.end_time, ps.day, all_for_check
        )

        if clashing:
            for clash in clashing:
                result.conflicts.append(
                    f"Conflict: {ps.day}  "
                    f"{_fmt12(ps.start_time)} – {_fmt12(ps.end_time)}  ({ps.job_name})"
                    f"  overlaps  "
                    f"{_fmt12(clash.start_time)} – {_fmt12(clash.end_time)}  ({clash.job_name})"
                )
            result.skipped.append(_skipped(ps, "Conflicts with an existing shift"))
            continue

        # 3d — Insert into database ──────────────────────────────────────────
        try:
            shift_id = db.insert_shift(
                job.id, ps.day, ps.start_time, ps.end_time
            )
            saved = Shift(
                id=shift_id,
                job_id=job.id,
                job_name=job.name,
                hourly_rate=job.hourly_rate,
                day=ps.day,
                start_time=ps.start_time,
                end_time=ps.end_time,
            )
            committed.append(saved)   # visible to later shifts in this batch

            result.imported.append({
                "id":         shift_id,
                "job_name":   job.name,
                "day":        ps.day,
                "start_time": ps.start_time,
                "end_time":   ps.end_time,
                "hours":      saved.hours,
            })

        except Exception as e:
            # Catch any unexpected database error without crashing
            result.errors.append(
                f"Database error saving {ps.job_name} "
                f"on {ps.day} {ps.start_time}–{ps.end_time}: {e}"
            )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _is_duplicate(ps: ParsedShift, job_id: int,
                   existing: list[Shift]) -> bool:
    """Return True if an identical shift already exists in the database."""
    for s in existing:
        if (s.job_id     == job_id        and
                s.day        == ps.day        and
                s.start_time == ps.start_time and
                s.end_time   == ps.end_time):
            return True
    return False


def _skipped(ps: ParsedShift, reason: str) -> dict:
    """Build a consistent 'skipped' dict for ImportResult.skipped."""
    return {
        "job_name":   ps.job_name,
        "day":        ps.day,
        "start_time": ps.start_time,
        "end_time":   ps.end_time,
        "reason":     reason,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — DISPLAY HELPER
# ─────────────────────────────────────────────────────────────────────────────

def print_import_result(result: ImportResult) -> None:
    """
    Print a clean, human-readable summary of an ImportResult to the terminal.

    GUI layers should read result.imported / result.conflicts etc. directly
    and render them in their own way — this function is for console use only.
    """
    W = 60
    print()
    print("═" * W)
    print("  SCHEDULE IMPORT  ·  Results")
    print("═" * W)

    # ── Successfully imported ─────────────────────────────────────────────────
    if result.imported:
        print(f"\n  ✓  {len(result.imported)} shift(s) saved\n")
        for s in result.imported:
            start = _fmt12(s["start_time"])
            end   = _fmt12(s["end_time"])
            print(f"       {s['job_name']:22s}  {s['day']:10s}  "
                  f"{start} – {end}  ({s['hours']}h)")
    else:
        print("\n  No shifts were saved.")

    # ── Conflicts ─────────────────────────────────────────────────────────────
    if result.conflicts:
        print(f"\n  ✗  {len(result.conflicts)} conflict(s) — not saved\n")
        for msg in result.conflicts:
            print(f"       {msg}")

    # ── Warnings ──────────────────────────────────────────────────────────────
    if result.warnings:
        print(f"\n  ⚠  {len(result.warnings)} warning(s)\n")
        for w in result.warnings:
            print(f"       {w}")

    # ── Errors ────────────────────────────────────────────────────────────────
    if result.errors:
        print(f"\n  ✗  {len(result.errors)} error(s)\n")
        for e in result.errors:
            print(f"       {e}")

    # ── Skipped summary ───────────────────────────────────────────────────────
    if result.skipped:
        print(f"\n  —  {len(result.skipped)} shift(s) skipped\n")
        for s in result.skipped:
            start = _fmt12(s["start_time"])
            end   = _fmt12(s["end_time"])
            print(f"       {s['job_name']:22s}  {s['day']:10s}  "
                  f"{start} – {end}  ←  {s['reason']}")

    print()
    print("═" * W)


# ─────────────────────────────────────────────────────────────────────────────
# DEMO — run this file directly
# python shift_parser.py
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    import tempfile
    from schedule_core import Scheduler

    # Use a fresh temp database so the demo is repeatable
    tmp_db = os.path.join(tempfile.gettempdir(), "fre_parser_demo.db")

    sched = Scheduler(db_path=tmp_db)
    sched.clear_week()

    # Create job profiles first (must exist before importing shifts)
    sched.add_job("Admissions",            hourly_rate=12.50)
    sched.add_job("Library",               hourly_rate=11.00)
    sched.add_job("International Office",  hourly_rate=15.00)

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 1 — Normal import
    # ─────────────────────────────────────────────────────────────────────────
    print("\n" + "·" * 60)
    print("  TEST 1 — Normal import")
    print("·" * 60)
    r = import_schedule_text("""
        Admissions: Mon 9-12 Wed 2-5 Fri 10-1
        Library: Tue 1-4 Thu 3-6
    """, db_path=tmp_db)
    print_import_result(r)

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 2 — Conflict against existing DB shifts
    # Mon 10-11 should clash with Admissions Mon 9-12 already saved above
    # ─────────────────────────────────────────────────────────────────────────
    print("·" * 60)
    print("  TEST 2 — Conflict with existing DB shift")
    print("·" * 60)
    r2 = import_schedule_text("""
        International Office: Mon 10-11
    """, db_path=tmp_db)
    print_import_result(r2)

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 3 — Batch-internal conflict
    # Two pasted shifts clash with each other (not with the DB)
    # ─────────────────────────────────────────────────────────────────────────
    print("·" * 60)
    print("  TEST 3 — Batch-internal conflict (two pasted shifts overlap)")
    print("·" * 60)
    r3 = import_schedule_text("""
        Admissions: Sat 10-2
        Library: Sat 11-3
    """, db_path=tmp_db)
    print_import_result(r3)

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 4 — Duplicate prevention
    # Try to re-import a shift that was already saved in Test 1
    # ─────────────────────────────────────────────────────────────────────────
    print("·" * 60)
    print("  TEST 4 — Duplicate prevention")
    print("·" * 60)
    r4 = import_schedule_text("""
        Admissions: Mon 9-12
    """, db_path=tmp_db)
    print_import_result(r4)

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 5 — Malformed / bad input resilience
    # Parser must not crash under any condition
    # ─────────────────────────────────────────────────────────────────────────
    print("·" * 60)
    print("  TEST 5 — Malformed input (must not crash)")
    print("·" * 60)
    r5 = import_schedule_text("""
        Mon 9-12
        Admissions: Moonday 9-12
        Admissions: Mon 25-26
        Admissions: Mon 9-9
        Admissions: Mon 10-10:05
        completely unreadable @@@
        Fake Job: Tue 1-4
    """, db_path=tmp_db)
    print_import_result(r5)

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 6 — Multi-line format
    # ─────────────────────────────────────────────────────────────────────────
    print("·" * 60)
    print("  TEST 6 — Multi-line job block")
    print("·" * 60)
    r6 = import_schedule_text("""
        International Office:
            Tue 10-2
            Thu 9-1
    """, db_path=tmp_db)
    print_import_result(r6)

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 7 — Night shift
    # ─────────────────────────────────────────────────────────────────────────
    print("·" * 60)
    print("  TEST 7 — Night shift (crosses midnight)")
    print("·" * 60)
    r7 = import_schedule_text("""
        Library: Sun 22-6
    """, db_path=tmp_db)
    print_import_result(r7)

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 8 — Empty input
    # ─────────────────────────────────────────────────────────────────────────
    print("·" * 60)
    print("  TEST 8 — Empty input")
    print("·" * 60)
    r8 = import_schedule_text("   ", db_path=tmp_db)
    print_import_result(r8)

    print("\nAll tests complete.\n")
