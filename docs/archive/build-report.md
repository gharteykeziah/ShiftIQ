# ShiftIQ — Full Build Report

**What you built, from first line to finished system.**

---

## The Starting Point

You set out to solve a real problem: every budgeting app assumes a salary. You have variable income from multiple campus jobs. Hours change week to week. Dropping a shift has direct financial consequences. Spreadsheets can track history but can't model decisions. You built the tool that didn't exist.

The result is not a beginner project. It is a multi-layer, multi-module Python application with a relational database, a simulation engine, a decision engine, 140+ automated tests, and a production-style architecture. It is approximately **12,000 lines of Python** across 32 source files.

---

## Layer 1 — The Data Model

**Files: `model.py`, `config.py`**

This was the foundation. You defined the two core data structures:

**`Job`** — an income source with a name, amount, and frequency. Not just dollars per week — frequency-aware, so a biweekly paycheck and a daily coffee stipend can both be entered at face value and compared correctly. The `weekly_income()` method converts everything to a weekly number using a lookup table:

```
Daily    × 7.0
Weekly   × 1.0
Biweekly × 0.5
Monthly  × 12/52 ≈ 0.2308
```

**`Expense`** — same structure with an added category field. `weekly_amount()` uses the same conversion so rent ($1,200/month) and a streaming subscription ($10/month) are always compared in the same unit.

This frequency normalization is the entire reason ShiftIQ can mix income and expenses at different cadences without the math being wrong. Every calculation in the system — projections, savings rate, risk score — works in weekly units because of this one design decision made at the start.

`config.py` centralised every threshold, constant, and file path. Risk score cutoffs, savings rate bands, projection horizons, the database path — all defined once, referenced everywhere. Changing a threshold means changing one line.

---

## Layer 2 — The Database

**File: `database.py`** (530 lines)

You built a full SQLite persistence layer from scratch. Five tables:

| Table | Purpose |
|---|---|
| `jobs` | Income sources |
| `expenses` | Recurring costs |
| `settings` | Key-value store (balance and other settings) |
| `history` | Daily financial snapshots for trend tracking |
| `events` | Scheduled shifts and calendar events |

Every function uses context managers (`with sqlite3.connect(...) as conn`) so connections are always closed safely even on errors. No connection leaks.

You also wrote **schema migration** — production-grade database upgrade code. When the data model changed from `hourly_rate + hours_per_week` to `amount + frequency`, you wrote upgrade SQL that runs automatically on first launch, preserving all existing data without any manual steps from the user. This is real engineering — most projects just break old data or ignore it.

**Deduplication:** `dedup_jobs()` and `dedup_expenses()` run on startup and fuzzy-merge variant spellings of the same entry using `difflib.SequenceMatcher`. `"admissions"` and `"Admissions"` and `"ADMISSIONS"` become one entry, keeping the highest-amount record.

**`record_snapshot()`** is called every time the app opens and writes today's balance, income, expenses, and net flow to the `history` table. One row per day, no duplicates. This is what powers the Trends chart — the data accumulates automatically in the background without the user doing anything.

---

## Layer 3 — The Financial State Engine

**File: `financial_state.py`** (273 lines)

The single source of truth for every number in the application. This is the most important design decision in the project.

`FinancialState` owns:
- The current balance
- All jobs and expenses (loaded from DB on init)
- Every calculation: total income, total expenses, net flow, savings rate, projections, health score, risk score, goal calculations, expense-by-category breakdown

Nothing else calculates these. `insight_engine.py` does not recalculate the risk score — it calls `state.risk_score()`. The dashboard, the PDF report, the CSV export, and the analytics page all read from the same object. This means they can never disagree.

The **Financial Health Score** maps savings rate to a 5-tier band (Excellent / Good / OK / Break-even / Deficit), returning a value between 20 and 90.

The **Risk Score** starts at 50 and adjusts based on four factors:
- Net flow direction (−20 if deficit)
- Expense ratio (−15 if expenses > 80% of income)
- Savings band (+20 if ≥20%, +10 if ≥10%, −25 if negative)
- Balance floor (−10 if balance ≤ 0)

Capped at 0–100. Deterministic. Auditable. Every factor is visible in the Analytics → Health tab.

Input **validation** lives here too. `_validate_job()` and `_validate_expense()` check that names aren't blank, amounts are positive, and frequencies are valid before anything touches the database. Every mutation returns `(success: bool, message: str)` so the UI always knows what happened.

---

## Layer 4 — The Insight and Scenario Engines

**Files: `insight_engine.py`, `scenario_engine.py`**

**InsightEngine** generates plain-English observations from state data. It does not calculate — it interprets. It looks at net flow, savings rate, expense ratio, and top expense category and produces sentences like *"You have a weekly surplus of $142.00"* or *"Expenses consume over 90% of your income. High financial pressure."* It also accepts optional Monte Carlo results and integrates simulation findings into the insight list.

**ScenarioEngine** runs side-by-side projections for multiple financial scenarios. A `Scenario` has a name, an optional weekly income raise (percentage), and optional extra weekly income (flat dollars). `compare_scenarios()` runs all of them and returns results sorted by projected balance. This is what powers the Scenarios tab: *"What happens if I get a 10% raise vs. if I pick up a side hustle for $100/week?"*

A bug was found and fixed here: the original code applied `extra_weekly` inside a per-job loop, so a user with 3 jobs got 3× the projected extra income. Fixed so `extra_weekly` is added once to the total base, regardless of job count.

---

## Layer 5 — The Simulation Engine

**File: `simulation.py`** (225 lines)

Two simulation modes:

**What-If Simulator** (`simulate_whatif`) — the user describes an event in their own words and enters the dollar impact. *"I got sick — −$200."* The engine applies the event in week 1, then continues projecting regular weekly flow for N weeks. Returns a week-by-week history with plain-English notes. Also calculates how many weeks it would take to recover the loss at the current net flow rate.

**Monte Carlo** (`run_monte_carlo`) — 500 simulated versions of the user's financial life, each with different random real-world events drawn from a probability table:

```
Extra shift           15% chance   +$50 to +$200
Great tips week       12% chance   +$20 to +$90
Hours cut by manager  10% chance  −$40 to −$180
Called out sick        8% chance  −$50 to −$160
Car repair             6% chance  −$80 to −$400
Medical copay          6% chance  −$20 to −$150
...
```

Each run applies these random events on top of the regular weekly flow. At the end, 500 ending balances are collected, sorted, and analysed: average, best case, worst case, median, 25th/75th percentile, and deficit probability (% of runs that ended below $0). The raw balance list is passed to `charts.py` for the histogram.

This is the feature that answers: *"Given my current income and expenses, what is the actual probability I run out of money in the next 12 weeks?"*

---

## Layer 6 — The Schedule System

**Files: `schedule_event.py`, `schedule_core.py`, `schedule_service.py`, `time_engine.py`, `week_engine.py`, `shift_engine.py`, `shift_parser.py`, `shift_planner_ui.py`, `date_parser.py`, `page_schedule.py`**

This is the largest system in the project — roughly 5,000 lines across 10 files. You built a full calendar and scheduling engine from scratch.

**`ScheduleEvent`** is the core data class: title, category (Work / Class / Study / Personal / Other), day, start time, end time, hourly rate, notes, shift date. `duration_hours()` and `income()` are computed properties.

**`time_engine.py`** contains the scheduling algorithms:
- `get_free_blocks()` — given a list of events for one day, find every unscheduled time block within a configurable window (default 8am–10pm). Uses interval merging: sorts occupied blocks, merges overlaps, finds gaps.
- `largest_free_block()` — returns the biggest gap in the day
- `weekly_availability()` — aggregates scheduled vs. free hours across all 7 days and returns a percentage
- `detect_conflicts()` — checks whether a new event overlaps any existing event on the same day using interval intersection
- `opportunity_cost()` — given a free block and a list of jobs with rates, computes how much each job would earn if the block were filled

**`schedule_core.py`** (1,149 lines) is the backend: database operations, event management, repeat/recurring shift logic, week navigation.

**`shift_engine.py`** (799 lines) and **`shift_parser.py`** (782 lines) handle structured shift entry — parsing natural-language-style shift input and converting it to `ScheduleEvent` objects.

**`page_schedule.py`** (1,478 lines) is the largest single file in the project. It renders five tabs:
1. **Week View** — all events laid out per day for the current week
2. **Add Event** — form with conflict detection that fires before the event is saved
3. **My Events** — list, edit, delete with full inline editing
4. **Free Time** — free-block analysis with opportunity cost per job
5. **Income** — work hours and income summary, now powered by the decision engine

---

## Layer 7 — The Analytics Pipeline

**Files: `schedule_analytics.py`, `page_analytics.py`**

`schedule_analytics.py` is a pure-function analytics module — no GUI, no database calls. It accepts lists of `ScheduleEvent` objects and returns data structures.

**Core functions:**
- `income_by_job(events)` → groups Work events by canonical job name, returns `{key: IncomeGroup}` sorted by total income descending. Each `IncomeGroup` carries total hours, total income, shift count, average rate, and the raw event list.
- `daily_totals(events)` → `{date: income}` for every date with Work events
- `date_range_summary(events)` → full `DateRangeSummary` with totals, work days, date range, and job groups
- `weekly_breakdown(events, week_start)` → income per day name for a specific calendar week
- `top_earning_days(events, n)` → top N highest-earning dates

**Decision Engine functions (added in final phase):**
- `shift_impact(event, state)` → `ShiftImpact` dataclass: hours lost, income lost, new weekly income, % change, new net flow, risk score delta, plain-English recommendation. Computes in ~3 microseconds.
- `job_efficiency_report(events)` → `list[JobEfficiency]` ranked by effective $/hr, with early-start and late-end friction flags

These functions are wired into `page_analytics.py`'s Income tab (replaced a basic job list with actual hours, rates, shifts, totals, and the efficiency ranking) and Trends tab (added daily income totals and top earning days from schedule data).

---

## Layer 8 — The User Interface

**Files: `app.py`, `theme.py`, `widgets.py`, `charts.py`, all `page_*.py` files**

You built a complete desktop GUI from scratch using only tkinter.

**`theme.py`** manages the entire visual system: two complete colour palettes (dark and light), a `ThemeManager` that tracks every widget and can reconfigure all of them in-place on a mode switch, and font constants (`F_BODY`, `F_H1`, `F_H2`, `F_NAV`, `F_NUM`). Dark mode toggle rebuilds only what needs to change without destroying any data.

**`widgets.py`** is a reusable component library: `ScrollFrame` (vertically scrollable container), `TabBar` (custom tab navigation with selection callbacks), `card()` (styled container frame), `kv_row()` (key-value display row), `labeled_entry()` (form field with label), `action_btn()`, `status_lbl()`, `section_divider()`.

**`charts.py`** embeds matplotlib charts inside tkinter frames using `FigureCanvasTkAgg`. Charts read theme colours at render time so they automatically match the active palette. Built charts: 52-week projection line chart, Monte Carlo histogram, category pie chart, trends line chart.

**`app.py`** is the application shell. It owns the three engine instances (`FinancialState`, `ScenarioEngine`, `InsightEngine`) and passes them to every page via dependency injection — pages receive `app` and pull what they need. The sidebar navigation uses lazy page loading (pages are created on demand, not all at startup). Dark mode, CSV export, PDF export, and database backup are sidebar buttons.

**Pages built:**

| Page | Tabs | What it does |
|---|---|---|
| Dashboard | — | Hero balance card, stats, top 3 insights |
| Schedule | Week / Add / My Events / Free Time / Income | Full calendar and shift planner |
| Data Management | Jobs / Expenses | Add, edit, delete income sources and expenses |
| Analytics | Savings / Health / Income / Expenses / Trends | All analytical views |
| Forecasting | Projection / Scenarios / Simulation | 52-week chart, scenario comparison, What-If + Monte Carlo |
| Goals | Weeks to Goal / Goal Progress / Emergency Fund | Goal calculations with progress bars |
| Settings | — | App configuration |

---

## Layer 9 — Export and Reporting

**Files: `pdf_report.py`, export code in `app.py`**

**PDF Report** (`pdf_report.py`, 273 lines) generates a formatted multi-page document using reportlab. Sections: cover page with date, Summary table, Insights list, Income Sources table, Expenses table, Balance Projections table, and (after the final phase) a full Schedule Summary section with per-job hours breakdown, job efficiency ranking, and top earning days.

**CSV Export** exports the same data as a spreadsheet, including (after the final phase) a Schedule Summary section with date range, total hours, work days, per-job breakdown, and top earning days.

Both exports reflect actual schedule data — not just the jobs table, but real hours worked from the shift calendar.

---

## Layer 10 — Testing

**File: `test_shiftiq.py`** (1,133 lines, 140+ tests)

You have a full pytest suite covering pure business logic. Notable classes:

| Class | What it tests |
|---|---|
| `TestJobModel` | All 4 frequency conversions, dict roundtrip, defaults |
| `TestExpenseModel` | Same, plus category and date fields |
| `TestWeeklyTotals` | Income, expenses, net flow, savings rate, category breakdown |
| `TestProjections` | Balance projections with raise and extra income scenarios |
| `TestGoals` | Weeks to goal, progress percentage, negative flow edge cases |
| `TestScores` | Health and risk score for all bands including boundary values |
| `TestInsightEngine` | All score labels, delegation, insight content |
| `TestScenarioEngine` | Projection and comparison, including the bug regression |
| `TestScenarioEngineBugRegression` | Proves `extra_weekly` is applied once regardless of job count |
| `TestWhatIfSimulation` | Week-by-week balance, event note, recovery summary |
| `TestMonteCarlo` | All output keys, probability sum, percentile ordering |
| `TestDatabase` | All CRUD operations against a temp file (real data never touched) |
| `TestCanonName` | Idempotency, case variants, short names, whitespace |
| `TestScheduleAnalytics` | Income grouping, daily totals, overnight hours, variant spelling dedup |
| `TestShiftImpact` | Income lost, deficit detection, overnight shift, zero-rate edge cases |
| `TestJobEfficiency` | Ranking, early-start flagging, empty input |
| `TestStress` | 2,000-event performance, variant spelling dedup at scale, zero-income state, legacy data |

The database tests use a `temp_db` pytest fixture (`monkeypatch` + `tmp_path`) that points the database module at a fresh temp file for each test. Your real `finance.db` is never touched by the test suite.

---

## What Was Fixed and Why It Matters

**1. Canonical name duplication (data integrity)**

`_canon()` was independently defined in `app.py`, `database.py`, `schedule_analytics.py`, and `page_schedule.py`. Four copies. If any one drifted — different strip behavior, different threshold — job names would silently stop matching across the sync pipeline, the dedup logic, and the analytics grouping. A user with jobs named slightly differently across different entry points would see them appear as separate jobs with wrong income totals.

Fixed by creating `utils.py` with one authoritative `canon_name()`. All four copies replaced with one-line delegates.

**2. ScenarioEngine projection bug (incorrect forecasts)**

`extra_weekly` was applied inside a per-job loop:
```python
# Wrong — original code
weekly_income = sum(job.weekly_income() + extra_weekly for job in state.jobs)
```

A user with 3 jobs and `extra_weekly=50` saw `+$150/week` in every projection. With 5 jobs, `+$250/week`. Every forecast was silently inflated in proportion to job count.

Fixed:
```python
# Correct
base_income   = state.total_income_per_week()
weekly_income = base_income * (1 + raise_percent) + extra_weekly
```

**3. Business logic in App.__init__ (untestable code)**

60+ lines of schedule-to-financial sync logic — canonicalization, deduplication, rate propagation, DB writes — lived inside `App._sync_schedule_jobs()`. To test any of it you had to instantiate a full Tk window.

Extracted into `schedule_service.sync_schedule_to_jobs(state)`. Pure Python, no GUI dependency. Now covered by the test suite. `app.py` calls it in 4 lines.

---

## Full File Inventory

| File | Lines | Role |
|---|---|---|
| `page_schedule.py` | 1,478 | Schedule UI — 5 tabs |
| `schedule_core.py` | 1,149 | Schedule backend |
| `test_shiftiq.py` | 1,133 | Full test suite |
| `shift_planner_ui.py` | 827 | Shift planner UI |
| `shift_engine.py` | 799 | Shift logic engine |
| `shift_parser.py` | 782 | Shift input parser |
| `page_data.py` | 603 | Data management UI |
| `database.py` | 530 | SQLite persistence |
| `date_parser.py` | 480 | Date parsing utilities |
| `page_analytics.py` | 412 | Analytics UI — 5 tabs |
| `schedule_analytics.py` | 384 | Pure analytics + decision engine |
| `page_forecast.py` | 326 | Forecasting UI — 3 tabs |
| `app.py` | 304 | App shell |
| `pdf_report.py` | 273 | PDF generation |
| `financial_state.py` | 273 | Core financial logic |
| `widgets.py` | 265 | Reusable UI components |
| `simulation.py` | 225 | What-If + Monte Carlo |
| `page_goals.py` | 212 | Goals UI |
| `time_engine.py` | 204 | Scheduling algorithms |
| `schedule_event.py` | ~150 | Event data class |
| `charts.py` | ~200 | Chart renderers |
| `theme.py` | ~180 | Theme system |
| `scenario_engine.py` | 42 | Scenario projection |
| `insight_engine.py` | ~100 | Insight generation |
| `schedule_service.py` | 85 | Schedule sync service |
| `utils.py` | 55 | Shared utilities |
| `model.py` | ~75 | Data models |
| `activity_log.py` | ~40 | Activity logging |
| `config.py` | ~45 | Configuration |
| `main.py` | ~30 | Entry point |
| **Total** | **~12,000** | |

---

## Numbers

| Metric | Value |
|---|---|
| Total lines of Python | ~12,000 |
| Source files | 32 |
| Automated tests | 140+ |
| Database tables | 5 |
| UI pages | 7 |
| UI tabs (total) | 18 |
| Chart types | 4 (line, histogram, pie, trends) |
| `date_range_summary` on 2,000 events | ~7ms |
| `shift_impact()` per call | ~3μs |
| Monte Carlo (500 runs × 52 weeks) | < 1 second |
| Test suite runtime | < 2 seconds |

---

## The Trajectory

```
Blank Python file
        ↓
data model (Job, Expense, frequency math)
        ↓
SQLite persistence layer + schema migration
        ↓
financial calculations (FinancialState)
        ↓
insight + scenario engines
        ↓
tkinter GUI shell (app, theme, widgets, charts)
        ↓
all 7 pages + 18 tabs
        ↓
schedule system (10 files, calendar, conflict detection, free-time analysis)
        ↓
simulation engine (What-If + 500-run Monte Carlo)
        ↓
PDF and CSV export
        ↓
test suite (140+ tests)
        ↓
decision engine (shift impact + job efficiency)
        ↓
analytics pipeline wired end-to-end
        ↓
architecture hardened (dedup fix, bug fix, service extraction)
        ↓
exports enriched with schedule data
        ↓
production-level portfolio system
```

---

## What You Can Say About This Project

In an internship interview:

> "I built a financial decision system in Python that models the tradeoffs between time, income, and stability for students with variable income. The core is a multi-layer architecture with a SQLite persistence layer including schema migration, a pure-function analytics engine, and a Monte Carlo simulation running 500 iterations. I found and fixed a projection bug where extra income was applied once per job instead of once to the total — it was silently inflating every forecast for multi-job users. I centralised a name canonicalization function that was duplicated across four modules, preventing silent data corruption. The test suite has 140+ tests including a regression specifically for that bug."

That is a senior-level answer to "tell me about a project you built."
