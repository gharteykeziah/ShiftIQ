# ShiftIQ — Senior Engineer Finishing Plan
**Target:** Production-level portfolio system. Google/Amazon internship tier.  
**Constraint:** No UI redesign. No schema rewrites. Integration and completion only.

---

## Code Review Findings (Pre-Plan)

Before the roadmap, three silent bugs and one architectural gap were found during review:

1. **`_canon()` is duplicated in 4 files** — `page_schedule.py`, `database.py`, `schedule_analytics.py`, and `app.py`. Any drift between them causes silent data corruption (job names that don't group correctly, income that doesn't sync). This is the highest-risk issue in the codebase.

2. **`ScenarioEngine.project_balance()` has an off-by-N bug** — `extra_weekly` is added inside the per-job loop, so a user with 2 jobs gets double the extra weekly income projected. `FinancialState.projected_income()` has the same pattern. They must agree.

3. **`schedule_analytics.py` is fully built but not wired into `page_analytics.py`** — The pure analytics functions (`income_by_job`, `daily_totals`, `date_range_summary`, `weekly_breakdown`) exist and are correct, but the Analytics page's Income and Trends tabs do not call them. The data pipeline is built; the connection is missing.

4. **`app.py._sync_schedule_jobs()` is 60+ lines of business logic inside the UI layer** — It owns canonicalization, deduplication, rate propagation, and DB writes. This belongs in a service module, not in `App.__init__`.

---

## Execution Roadmap

### Step 1 — Centralize `_canon()` into a shared utility module
**Impact: Critical / Blocking**

**What to build:**  
Create `utils.py` with a single authoritative `canon_name(name: str) -> str` function. Remove all four duplicate definitions.

**Why it matters:**  
Right now, if any one copy of `_canon()` drifts — a one-character change in the threshold, a different strip behavior — job names stop matching across modules. Job income from the Schedule page won't sync to the Data page. `dedup_jobs()` in `database.py` silently keeps duplicates. This is a data integrity bug disguised as a style issue.

**Where it connects:**
```
utils.py           ← NEW: canon_name(), normalize_job_name()
database.py        ← replace _canon_db() with canon_name()
schedule_analytics.py ← replace _canon() with canon_name()
app.py             ← replace _canon() in _sync_schedule_jobs()
page_schedule.py   ← replace _canon() and _normalize_job_name() (keep _normalize_job_name, just call canon_name internally)
```

**Implementation:**
```python
# utils.py
def canon_name(name: str) -> str:
    """
    Canonical job/expense name.
    strip → drop trailing 's' if stem ≥ 5 chars → Title Case.
    'Admissions', 'admission', 'ADMISSIONS' → 'Admission'
    """
    n = name.strip()
    if len(n) > 4 and n.lower().endswith("s"):
        n = n[:-1]
    return n.title()
```

---

### Step 2 — Extract `_sync_schedule_jobs()` into a service module
**Impact: High / Architecture**

**What to build:**  
Create `schedule_service.py`. Move all schedule-to-financial sync logic out of `app.py` into a `sync_schedule_to_jobs(state: FinancialState) -> int` function that returns the count of jobs synced.

**Why it matters:**  
Business logic in the UI layer cannot be tested without instantiating a full Tk window. This is the primary reason the system is hard to test. Extracting it makes the sync callable from tests, from a CLI, from a background thread, or from any future entry point. It also makes `app.py` dramatically simpler.

**Where it connects:**
```
schedule_service.py   ← NEW: sync_schedule_to_jobs(state)
app.py                ← _sync_schedule_jobs() becomes: schedule_service.sync_schedule_to_jobs(self.state)
test_shiftiq.py           ← can now test sync logic without Tk
```

**Signature:**
```python
# schedule_service.py
import database as db
from utils import canon_name
from model import Job

def sync_schedule_to_jobs(state) -> int:
    """
    Sum Work event hours per canonical job name, compute weekly income,
    and upsert into state.jobs + DB. Returns count of jobs updated.
    """
    ...
```

---

### Step 3 — Wire `schedule_analytics` into `page_analytics` Income + Trends tabs
**Impact: High / Visible Feature Completion**

**What to build:**  
In `page_analytics.py`, rewrite `_income()` and `_trends()` to call `schedule_analytics.date_range_summary()` and `schedule_analytics.weekly_breakdown()` with real event data from the database.

**Why it matters:**  
`schedule_analytics.py` is one of the best-written modules in this project — pure functions, clean types, overnight-aware hour math. It produces `DateRangeSummary`, `IncomeGroup`, and per-day breakdowns. None of this appears in the UI. The Income tab currently shows basic job totals from `FinancialState`. It should show per-job hours, rates, and shift counts from actual schedule data. The Trends tab should show income over time from `db.load_history()` and `schedule_analytics.daily_totals()`.

**Where it connects:**
```
page_analytics.py   ← _income(): call db.get_events() + schedule_analytics.income_by_job()
page_analytics.py   ← _trends(): call db.load_history() for balance trend + schedule_analytics.daily_totals() for income trend
schedule_analytics.py ← no changes needed (already correct)
charts.py           ← add bar_chart(data: dict[str, float]) if not already present
```

**What the Income tab should show per job:**
- Job name, hourly rate, total hours this period, total earned, shift count
- Sorted by total_income descending (already the default from `income_by_job()`)

---

### Step 4 — Fix `ScenarioEngine` + `FinancialState` projection bug
**Impact: High / Correctness**

**What to build:**  
Fix `ScenarioEngine.project_balance()` so `extra_weekly` is added once to the total weekly income, not once per job. Then verify `FinancialState.projected_income()` matches the same logic.

**Why it matters:**  
A user with 3 jobs gets 3× the `extra_weekly` income in projections. This silently inflates every forecast and goal timeline. It's a portfolio-killer if a recruiter runs the app and checks the math.

**Where it connects:**
```
scenario_engine.py    ← fix project_balance() and compare_scenarios()
financial_state.py    ← verify projected_income() applies raise/extra once to total
test_shiftiq.py           ← add parametrized test: 1 job vs 3 jobs with same extra_weekly must produce same total
```

**Fix:**
```python
# scenario_engine.py — corrected
def project_balance(self, state, weeks, scenario=None):
    extra_weekly  = scenario.extra_weekly  if scenario else 0.0
    raise_percent = scenario.raise_percent if scenario else 0.0
    base_income   = state.total_income_per_week()           # sum once
    weekly_income = base_income * (1 + raise_percent) + extra_weekly  # add once
    net           = weekly_income - state.total_expense_per_week()
    return round(state.current_balance() + net * weeks, 2)
```

---

### Step 5 — Build the Decision Engine: Shift Impact Analyzer
**Impact: High / Differentiator**

**What to build:**  
Add `shift_impact(event, state) -> ShiftImpact` to `schedule_analytics.py`. Surface it in `page_schedule.py`'s Income tab as a "What if I remove this shift?" calculator.

**Why it matters:**  
This is what turns ShiftIQ from a tracker into a decision system. A student deciding whether to swap a shift or take a day off can see the exact income lost, how their weekly total changes, and what the new risk score would be. This is the feature that belongs in a portfolio description.

**Where it connects:**
```
schedule_analytics.py  ← add ShiftImpact dataclass + shift_impact()
page_schedule.py       ← Income tab: add shift list with "Impact" button per shift
financial_state.py     ← read current risk_score() for delta comparison
```

**Implementation (pure, no GUI):**
```python
# schedule_analytics.py

from dataclasses import dataclass

@dataclass
class ShiftImpact:
    hours_lost:        float   # hours in the removed shift
    income_lost:       float   # dollars lost
    new_weekly_income: float   # income after removal
    weekly_income_pct_change: float  # e.g. -12.5 (percent)
    new_net_flow:      float   # new net_weekly_flow after removal
    risk_delta:        int     # new_risk_score - current_risk_score (negative = worse)
    recommendation:    str     # plain-English one-liner

def shift_impact(event, state) -> ShiftImpact:
    """
    Compute the financial impact of removing one Work shift event.
    state: FinancialState instance (read-only).
    """
    hours       = _shift_hours(event)
    rate        = event.hourly_rate or 0.0
    income_lost = round(hours * rate, 2)

    current_weekly = state.total_income_per_week()
    new_weekly     = round(current_weekly - income_lost, 2)

    pct_change = ((new_weekly - current_weekly) / current_weekly * 100
                  if current_weekly else 0.0)

    new_net = round(new_weekly - state.total_expense_per_week(), 2)

    # Estimate new risk score without mutating state
    old_risk    = state.risk_score()
    delta_score = 0
    if new_net < 0 and state.net_weekly_flow() >= 0:
        delta_score -= 20   # flipped to deficit
    elif new_weekly > 0:
        new_ratio = state.total_expense_per_week() / new_weekly
        if new_ratio > 0.8:
            delta_score -= 15

    if pct_change < -15:
        rec = f"Removing this shift cuts weekly income by {abs(pct_change):.1f}%. Consider replacing it."
    elif new_net < 0:
        rec = "Removing this shift puts you in a weekly deficit. Not recommended."
    else:
        rec = f"Removing this shift is manageable. You still net ${new_net:.2f}/week."

    return ShiftImpact(
        hours_lost=hours,
        income_lost=income_lost,
        new_weekly_income=new_weekly,
        weekly_income_pct_change=round(pct_change, 1),
        new_net_flow=new_net,
        risk_delta=delta_score,
        recommendation=rec,
    )
```

---

### Step 6 — Build the Decision Engine: Job Efficiency Score
**Impact: Medium-High / Differentiator**

**What to build:**  
Add `job_efficiency_report(events, state) -> list[JobEfficiency]` to `schedule_analytics.py`. Show it in the Income tab as a ranked comparison table.

**Why it matters:**  
A student working two jobs needs to know which one is worth more per hour of their time *factoring in scheduling cost* (e.g., a job that pays $12/hr but always puts you in at 7am on Mondays has a hidden cost). This metric — income per hour adjusted for scheduling friction — is non-obvious and demonstrates systems thinking.

**Where it connects:**
```
schedule_analytics.py  ← add JobEfficiency dataclass + job_efficiency_report()
page_schedule.py       ← Income tab: add a ranked "Job Comparison" card
```

**Implementation:**
```python
@dataclass
class JobEfficiency:
    name:            str
    total_hours:     float
    total_income:    float
    income_per_hour: float    # raw $/hr
    early_starts:    int      # shifts starting before 08:00
    late_ends:       int      # shifts ending after 22:00
    efficiency_note: str      # plain-English summary

def job_efficiency_report(events: list, state=None) -> list["JobEfficiency"]:
    """
    Rank jobs by income_per_hour. Flag scheduling friction (early/late).
    Returns list sorted by income_per_hour descending.
    """
    groups = income_by_job(events)
    results = []
    for key, group in groups.items():
        early = sum(
            1 for ev in group.shifts
            if int(ev.start_time.split(":")[0]) < 8
        )
        late = sum(
            1 for ev in group.shifts
            if int(ev.end_time.split(":")[0]) >= 22
        )
        iph = group.avg_rate  # already computed
        if early > 0 and late > 0:
            note = f"High friction: {early} early starts, {late} late ends."
        elif early > 0:
            note = f"{early} early-morning shifts. Good pay, high scheduling cost."
        elif late > 0:
            note = f"{late} late shifts. Consider impact on rest and study."
        else:
            note = "Favorable scheduling pattern."

        results.append(JobEfficiency(
            name=group.name,
            total_hours=group.total_hours,
            total_income=group.total_income,
            income_per_hour=iph,
            early_starts=early,
            late_ends=late,
            efficiency_note=note,
        ))
    return sorted(results, key=lambda j: j.income_per_hour, reverse=True)
```

---

### Step 7 — Connect `history` table to the Trends tab with a real line chart
**Impact: Medium / Completeness**

**What to build:**  
In `page_analytics._trends()`, load `db.load_history()` and render a balance-over-time line chart using `charts.py`. If fewer than 3 snapshots exist, show a "Keep using ShiftIQ daily to build your trend data" message instead of an empty chart.

**Why it matters:**  
`record_snapshot()` is already called on every app launch (in `FinancialState.__init__`), so the data accumulates automatically. The history table likely already has records. An empty Trends tab when data exists is a silent gap that interviewers will notice.

**Where it connects:**
```
page_analytics.py   ← _trends(): load db.load_history(), render line chart
charts.py           ← confirm/add line_chart(labels, values, title, color)
database.py         ← load_history() already exists (no changes needed)
```

---

### Step 8 — Minimal Testing Strategy
**Impact: Medium / Portfolio Credibility**

**What to build:**  
Expand `test_shiftiq.py` into a proper pytest suite. Target pure/business logic only — no Tk, no GUI.

**Why it matters:**  
A repo with no tests signals "prototype." A repo with 20 focused tests on core business logic signals "engineer." You don't need 100% coverage — you need the right tests on the right things.

**Pytest structure:**
```
test_shiftiq.py
├── TestCanonName              ← utils.py
├── TestJobModel               ← model.py weekly_income()
├── TestExpenseModel           ← model.py weekly_amount()
├── TestFinancialState         ← financial_state.py calculations
├── TestScenarioEngine         ← scenario_engine.py (bug regression)
├── TestScheduleAnalytics      ← schedule_analytics.py pure functions
├── TestShiftImpact            ← the new decision engine
└── TestSyncService            ← schedule_service.sync_schedule_to_jobs()
```

**Priority tests (write these first):**

```python
# test_shiftiq.py — priority tests

import pytest
from utils import canon_name
from model import Job, Expense
from financial_state import FinancialState
from scenario_engine import ScenarioEngine, Scenario
import schedule_analytics as sa


# ── 1. canon_name ──────────────────────────────────────────────────────────
class TestCanonName:
    def test_strips_trailing_s(self):
        assert canon_name("admissions") == "Admission"

    def test_preserves_short_names(self):
        assert canon_name("OIP") == "Oip"   # len == 3, no strip

    def test_title_cases(self):
        assert canon_name("DINING SERVICES") == "Dining Service"

    def test_idempotent(self):
        name = "Dining Service"
        assert canon_name(canon_name(name)) == canon_name(name)


# ── 2. Model frequency math ────────────────────────────────────────────────
class TestJobModel:
    def test_weekly_is_passthrough(self):
        assert Job("x", 500, "Weekly").weekly_income() == 500

    def test_biweekly_halved(self):
        assert Job("x", 1000, "Biweekly").weekly_income() == 500

    def test_monthly_approximation(self):
        j = Job("x", 1040, "Monthly")
        assert abs(j.weekly_income() - 240.0) < 1.0


# ── 3. FinancialState calculations ────────────────────────────────────────
class TestFinancialStateCalc:
    def _make_state(self):
        """Build a state without DB I/O."""
        from unittest.mock import patch
        with patch("database.init_db"), \
             patch("database.load_balance", return_value=1000.0), \
             patch("database.load_jobs",    return_value=[]), \
             patch("database.load_expenses", return_value=[]), \
             patch("database.record_snapshot"):
            s = FinancialState()
        s.jobs     = [Job("Job A", 500, "Weekly"), Job("Job B", 300, "Weekly")]
        s.expenses = [Expense("Rent", 800, "Housing", "", "Monthly")]
        s.balance  = 1000.0
        return s

    def test_total_income(self):
        s = self._make_state()
        assert s.total_income_per_week() == 800.0

    def test_net_flow(self):
        s = self._make_state()
        rent_weekly = 800 * (12/52)
        assert abs(s.net_weekly_flow() - (800.0 - rent_weekly)) < 0.01

    def test_project_balance_zero_weeks(self):
        s = self._make_state()
        assert s.project_balance(0) == s.balance


# ── 4. ScenarioEngine bug regression ──────────────────────────────────────
class TestScenarioEngineBugRegression:
    """extra_weekly must be added once, not once per job."""

    def _state_with_n_jobs(self, n):
        from unittest.mock import patch
        with patch("database.init_db"), \
             patch("database.load_balance", return_value=0.0), \
             patch("database.load_jobs",    return_value=[]), \
             patch("database.load_expenses", return_value=[]), \
             patch("database.record_snapshot"):
            s = FinancialState()
        s.jobs     = [Job(f"Job {i}", 100, "Weekly") for i in range(n)]
        s.expenses = []
        s.balance  = 0.0
        return s

    def test_extra_weekly_independent_of_job_count(self):
        """With extra_weekly=50, projected balance must not scale with job count."""
        sc = ScenarioEngine()
        scenario = Scenario("Test", extra_weekly=50.0)
        b1 = sc.project_balance(self._state_with_n_jobs(1), weeks=1, scenario=scenario)
        b3 = sc.project_balance(self._state_with_n_jobs(3), weeks=1, scenario=scenario)
        # b3 has 3x income base but same extra_weekly=50
        # b1 = 100 + 50 = 150, b3 = 300 + 50 = 350 (not 300 + 150 = 450)
        assert b3 == pytest.approx(350.0, abs=0.01)
        assert b1 == pytest.approx(150.0, abs=0.01)


# ── 5. ShiftImpact decision engine ────────────────────────────────────────
class TestShiftImpact:
    def _make_event(self, start="09:00", end="17:00", rate=15.0):
        from schedule_event import ScheduleEvent
        return ScheduleEvent(
            title="Test Job", category="Work", day="Monday",
            start_time=start, end_time=end,
            hourly_rate=rate, notes="", shift_date="2026-06-16"
        )

    def _make_state(self, weekly_income=800.0, weekly_expenses=600.0, balance=500.0):
        from unittest.mock import MagicMock
        s = MagicMock()
        s.total_income_per_week.return_value   = weekly_income
        s.total_expense_per_week.return_value  = weekly_expenses
        s.net_weekly_flow.return_value         = weekly_income - weekly_expenses
        s.risk_score.return_value              = 65
        s.balance = balance
        return s

    def test_basic_8h_shift(self):
        ev     = self._make_event("09:00", "17:00", rate=15.0)
        state  = self._make_state(weekly_income=800.0)
        impact = sa.shift_impact(ev, state)
        assert impact.hours_lost   == pytest.approx(8.0)
        assert impact.income_lost  == pytest.approx(120.0)
        assert impact.new_weekly_income == pytest.approx(680.0)

    def test_deficit_triggers_warning(self):
        ev    = self._make_event(rate=50.0)   # 8h × $50 = $400
        state = self._make_state(weekly_income=500.0, weekly_expenses=450.0)
        impact = sa.shift_impact(ev, state)
        assert impact.new_net_flow < 0
        assert "deficit" in impact.recommendation.lower()

    def test_overnight_shift_hours(self):
        ev = self._make_event(start="22:00", end="06:00", rate=20.0)
        assert sa._shift_hours(ev) == pytest.approx(8.0)


# ── 6. schedule_analytics pure functions ─────────────────────────────────
class TestScheduleAnalytics:
    def _events(self):
        from schedule_event import ScheduleEvent
        return [
            ScheduleEvent("Job A", "Work", "Monday",    "09:00", "17:00", 15.0, "", shift_date="2026-06-16"),
            ScheduleEvent("Job A", "Work", "Wednesday", "09:00", "13:00", 15.0, "", shift_date="2026-06-18"),
            ScheduleEvent("Job B", "Work", "Tuesday",   "10:00", "14:00", 20.0, "", shift_date="2026-06-17"),
            ScheduleEvent("Class", "School", "Monday",  "08:00", "09:00", 0.0,  "", shift_date="2026-06-16"),
        ]

    def test_income_by_job_ignores_non_work(self):
        groups = sa.income_by_job(self._events())
        assert "Class" not in "".join(groups.keys())

    def test_income_by_job_groups_correctly(self):
        groups = sa.income_by_job(self._events())
        assert "Job A" in groups or "Job" in "".join(groups.keys())

    def test_daily_totals_sums_per_date(self):
        totals = sa.daily_totals(self._events())
        assert "2026-06-16" in totals
        assert totals["2026-06-16"] == pytest.approx(8 * 15.0)

    def test_date_range_summary_total_hours(self):
        summary = sa.date_range_summary(self._events())
        assert summary.total_hours == pytest.approx(8 + 4 + 4)   # 16h work
```

**Run with:** `pytest test_shiftiq.py -v --tb=short`

---

### Step 9 — Data Stress Test Plan
**Impact: Medium / Robustness**

**Goal:** Validate that the system handles messy, real-world schedule data without silent failures.

**Stress scenarios to simulate:**

**1. Duplicate job names with variant spellings**
```python
events = [
    ScheduleEvent("admissions", "Work", ..., hourly_rate=14.0),
    ScheduleEvent("Admissions", "Work", ..., hourly_rate=14.0),
    ScheduleEvent("ADMISSIONS", "Work", ..., hourly_rate=0.0),  # rate missing
]
# Expected: income_by_job() returns exactly ONE group, rate=14.0, hours summed
```

**2. Overnight shift crossing midnight**
```python
ev = ScheduleEvent("Night Job", "Work", "Friday", "23:00", "07:00", 18.0, ...)
# Expected: _shift_hours(ev) == 8.0, NOT -16.0 or 0.0
```

**3. Zero-rate shifts mixed with rated shifts**
```python
# Job A has 3 shifts at $15/hr and 1 shift at $0 (rate not yet entered)
# Expected: income_by_job() uses $15 for all, not $0 for the missing one
# Validate: IncomeGroup.rate propagation in income_by_job()
```

**4. Events with no shift_date (legacy data)**
```python
ev_legacy = ScheduleEvent("Old Job", "Work", "Monday", "09:00", "17:00", 12.0, "", shift_date="")
# Expected: daily_totals() skips it (date_s is empty), does NOT crash
# Expected: income_by_job() still counts hours (it doesn't require shift_date)
```

**5. Single-job state with extra_weekly scenario**
```python
# ScenarioEngine: 1 job vs 3 jobs with same scenario must produce proportional results
# (regression for the bug fixed in Step 4)
```

**6. Large event set (performance)**
```python
import random, datetime
events = []
for i in range(5000):
    d = datetime.date(2025, 1, 1) + datetime.timedelta(days=random.randint(0, 365))
    events.append(ScheduleEvent(
        title=random.choice(["Job A", "Job B", "job a", "JOB B"]),
        category="Work", day=d.strftime("%A"),
        start_time=f"{random.randint(6,14):02d}:00",
        end_time=f"{random.randint(15,22):02d}:00",
        hourly_rate=random.choice([0.0, 14.0, 15.0, 20.0]),
        notes="", shift_date=d.isoformat()
    ))
# Expected: date_range_summary(events) completes in < 100ms
# Expected: income_by_job() returns exactly 2 groups (A and B), not 4
```

**7. All-zero income state**
```python
state.jobs = []
# Expected: savings_rate() returns 0.0, NOT ZeroDivisionError
# Expected: risk_score() returns a valid int
# Expected: shift_impact(ev, state) returns income_lost=0.0, no crash
```

**How to run the stress suite:**
```python
# test_shiftiq.py — add a TestStress class
import time

class TestStress:
    def test_large_event_performance(self):
        # ... generate 5000 events ...
        start = time.perf_counter()
        summary = sa.date_range_summary(events)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1, f"date_range_summary took {elapsed:.3f}s on 5000 events"

    def test_dedup_on_variant_spellings(self):
        # ... create events with admission/Admissions/ADMISSIONS ...
        groups = sa.income_by_job(events)
        assert len(groups) == 1
```

---

### Step 10 — Tie schedule analytics into PDF/CSV export
**Impact: Low-Medium / Polish**

**What to build:**  
In `pdf_report.py` and `app.py`'s `_export_csv()`, add a "Schedule Summary" section using `schedule_analytics.date_range_summary(db.get_events())`.

**Why it matters:**  
A PDF report that only shows jobs and expenses — but not the actual hours worked, shift breakdown, or income-per-job from the schedule — is incomplete. A recruiter running this app should see a full financial picture in every export.

**Where it connects:**
```
pdf_report.py     ← add schedule_summary section: hours by job, total earned, date range
app.py            ← _export_csv(): append rows from date_range_summary()
schedule_analytics.py ← no changes (already returns all needed data)
```

**New CSV rows to add:**
```
SCHEDULE SUMMARY
Date Range, [start] to [end]
Total Hours Worked, [X]
Total Schedule Income, $[X]
[Job Name], [hours], [rate], $[income]
```

---

## Decision Engine Summary

Two features were added (Steps 5 and 6):

| Feature | Module | Input | Output |
|---|---|---|---|
| Shift Removal Impact | `schedule_analytics.py` | one `ScheduleEvent` + `FinancialState` | `ShiftImpact` dataclass |
| Job Efficiency Score | `schedule_analytics.py` | event list + optional state | `list[JobEfficiency]` ranked by $/hr |

Both are pure functions with no GUI coupling. Both are testable in isolation. Both surface in `page_schedule.py`'s Income tab as a decision layer — not just a display.

---

## Implementation Order (tightest dependency first)

```
Step 1  utils.py (canon_name)                    ← unblocks everything
Step 4  ScenarioEngine bug fix                   ← correctness before feature work
Step 2  schedule_service.py                      ← depends on Step 1
Step 5  ShiftImpact (schedule_analytics.py)      ← depends on Step 1
Step 6  JobEfficiency (schedule_analytics.py)    ← depends on Step 5
Step 3  Wire analytics into page_analytics       ← depends on Steps 1, 2
Step 7  Trends tab history chart                 ← depends on Step 3
Step 8  Testing (write as you go, finish here)   ← depends on Steps 1–6
Step 9  Stress tests                             ← depends on Step 8
Step 10 Export enrichment                        ← last, lowest risk
```

---

## Portfolio Framing

When describing this project:

> "Built a personal financial decision system in Python/Tkinter with SQLite persistence. Designed a shift impact analysis engine that computes real-time income loss, net flow delta, and risk score change from removing any scheduled shift. Implemented canonical name deduplication across a multi-module pipeline to prevent silent data corruption. Wrote a pytest suite covering pure business logic including a regression test for a projection bug affecting multi-job users."

That framing hits: system design, data integrity, decision logic, testing, and bug identification — all from one project.
