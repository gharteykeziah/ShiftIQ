# Financial Reality Engine

**A decision intelligence system that models the relationship between time allocation, variable income, and financial stability. Built for people whose income is a function of their schedule, not a fixed salary.**

---

## Screenshots

### Dashboard
![Dashboard](screenshots/dashboard.png)
*Real-time financial snapshot — balance, weekly income/expenses, risk score, and health score.*

### Schedule — Week View
![Schedule Week View](screenshots/schedule_week.png)
*Full life planner: color-coded Study, Class, Work, and Personal events. Weekly hours and availability at a glance.*

### Analytics — Income Breakdown
![Analytics Income](screenshots/analytics_income.png)
*Income derived from scheduled shifts — hours, rate, and total per job with efficiency ranking.*

### Forecasting — Monte Carlo Simulation
![Monte Carlo](screenshots/forecasting.png)
*500 parallel futures: most likely outcome, best/worst case, and probability of running out of money.*

### Schedule — Import
![Schedule Import](screenshots/schedule_import.png)
*Paste any schedule format — natural date headers, AM/PM times, inline rates — auto-detected and categorized.*

---

## Key Features

| Feature | What it does |
|---|---|
| **Decision Engine** | Computes the exact financial impact of dropping any shift in real time |
| **Monte Carlo Simulation** | Runs 500 parallel futures to measure deficit probability over a chosen horizon |
| **Schedule-Derived Income** | Income is calculated from shifts, not manually entered — changes to the schedule instantly update projections |
| **Financial Risk Score** | Multi-factor score (0–100) based on net flow, expense ratio, savings rate, and balance |
| **Free Time Analysis** | Identifies open time blocks and computes opportunity cost per job |
| **Job Efficiency Ranking** | Ranks every job by effective $/hr with early-start and late-end friction flags |
| **What-If Simulator** | Models any one-time event (car repair, bonus, missed shift) and projects recovery time |
| **PDF + CSV Export** | Full reports including per-job income breakdown, efficiency ranking, and top earning days |
| **Dark / Light Mode** | Full theme system with live toggle — no window reload |
| **Automatic Deduplication** | Fuzzy-matches variant spellings of the same job name on startup |

---

## Why This Exists

Every personal finance tool makes the same assumption: income is a known constant. You enter it once, it stays fixed, and the app calculates around it.

That model fails for the roughly 70 million Americans in variable-income work — gig workers, shift employees, hourly contractors, freelancers, campus workers. Their income is not a number. It is a function:

```
income = Σ(shift_hours × hourly_rate)  across all jobs for the week
```

FRE reframes the problem. Instead of asking *"how much money do you have?"*, the system asks *"how does your time allocation affect your financial stability?"*

Drop a shift → weekly income updates → savings rate updates → risk score updates → 52-week projection updates. The entire financial picture adjusts to reflect one scheduling decision, before it is made.

**Who this is built for:**

| User Type | How FRE Applies |
|---|---|
| Campus / part-time workers | Multiple jobs, variable hours, shift-based scheduling |
| Gig economy workers | Income = hours on platform × rate — no fixed paycheck |
| Hourly employees | Hours change weekly; shift drop/add has direct income impact |
| Shift workers | Nurses, retail, hospitality — schedule change = income change |
| Freelancers | Multiple clients at different rates; irregular income flow |
| Contract workers | Project-based gaps, rate variability across engagements |

---

## Tech Stack

| Layer | Technology | Note |
|---|---|---|
| Language | Python 3.10+ | Type hints throughout |
| GUI | tkinter (stdlib) | No external UI framework |
| Database | SQLite via sqlite3 (stdlib) | No ORM |
| Charts | matplotlib via FigureCanvasTkAgg | Embedded in tkinter frames |
| PDF Export | reportlab | 7-section reports with schedule data |
| Tests | pytest | 140+ tests, no GUI required |

No web framework. No ORM. No UI toolkit beyond what ships with Python.

---

## System Architecture

```
                         ┌─────────────────────┐
                         │   Schedule Input     │
                         │   (page_schedule)    │
                         └──────────┬──────────┘
                                    │  ScheduleEvent(title, shift_date,
                                    │  start_time, end_time, hourly_rate)
                         ┌──────────▼──────────┐
                         │  Schedule Service    │  ← sync, dedup, rate propagation
                         │  (schedule_service)  │
                         └──────────┬──────────┘
                                    │  Job(name, weekly_amount)
               ┌────────────────────▼────────────────────┐
               │          Schedule Analytics              │
               │  income_by_job · daily_totals            │  ← pure functions
               │  shift_impact · job_efficiency_report    │     no GUI / no DB
               └────────────────────┬────────────────────┘
                                    │
               ┌────────────────────▼────────────────────┐
               │           Financial State               │
               │  total_income · net_flow · savings_rate │  ← single source of truth
               │  health_score · risk_score · projections│
               └──────────┬──────────────────┬───────────┘
                          │                  │
              ┌───────────▼───┐     ┌────────▼──────────┐
              │ Insight Engine │     │  Scenario Engine   │
              │ Simulation     │     │  Monte Carlo (500) │
              └───────────┬───┘     └────────┬──────────┘
                          │                  │
               ┌──────────▼──────────────────▼──────────┐
               │              UI Pages                   │
               │  Dashboard · Schedule · Analytics       │
               │  Forecasting · Goals · Data Management  │
               └─────────────────────────────────────────┘
                          │                  │
               ┌──────────▼───┐   ┌──────────▼──────────┐
               │  PDF Export  │   │  CSV Export          │
               │ (reportlab)  │   │  (schedule-enriched) │
               └──────────────┘   └─────────────────────┘
```

**Architectural invariants enforced throughout:**
- All financial calculations live only in `financial_state.py` — no page, export, or engine recalculates them
- Analytics functions in `schedule_analytics.py` are pure: accept event lists, return data structures, make zero DB or GUI calls
- Business logic is extracted from UI classes — the 140+ test suite runs without a window
- Name canonicalization has exactly one implementation (`utils.canon_name`) imported by every module that touches names

---

## Core Engines

### Decision Engine

The capability that separates FRE from a tracker.

**`shift_impact(event, state) → ShiftImpact`** — given any scheduled shift, computes in ~3 microseconds:

```python
@dataclass
class ShiftImpact:
    hours_lost:               float
    income_lost:              float
    new_weekly_income:        float
    weekly_income_pct_change: float   # negative = income drop
    new_net_flow:             float
    risk_delta:               int     # negative = stability decreased
    recommendation:           str     # plain-English action guidance
```

Pure function. Reads state, never mutates it. Tested with overnight shifts, zero-rate edge cases, and deficit-crossing scenarios.

**`job_efficiency_report(events) → list[JobEfficiency]`** — ranks every job by effective $/hr across all recorded shifts. Flags early-morning starts (before 08:00) and late ends (after 22:00) as scheduling friction.

---

### Financial State Engine

Single source of truth for every number in the application.

`financial_state.py` owns: weekly income, weekly expenses, net flow, savings rate, projections, health score (0–100), risk score (0–100). No other module recalculates these. `insight_engine.py` calls `state.risk_score()` — it does not reimplement it.

**Risk score model** — starts at 50, bounded 0–100:

```
net_weekly_flow < 0          → −20
expenses / income > 0.80     → −15
savings_rate ≥ 20%           → +20
savings_rate ≥ 10%           → +10
savings_rate < 0%            → −25
balance ≤ 0                  → −10
```

Every factor is visible in Analytics → Health. The score is deterministic and auditable.

---

### Simulation Engine

**What-If Simulator** — models any one-time financial event and projects balance week-by-week over a chosen horizon. Returns recovery time at current net flow rate.

**Monte Carlo** — 500 parallel simulations of the next N weeks, each with independently randomised life events:

```
Extra shift       15% chance   +$50 to +$200
Great tips week   12% chance   +$20 to +$90
Hours cut         10% chance   −$40 to −$180
Called out sick    8% chance   −$50 to −$160
Car repair         6% chance   −$80 to −$400
Medical copay      6% chance   −$20 to −$150
```

Returns: `average · best_case · worst_case · median · p25 · p75 · deficit_probability · plain_summary · ending_balances`

Answers: *"Given my current income pattern, what is the probability I run out of money in the next 12 weeks?"* — not an estimate, a measurement across 500 simulated futures.

---

### Schedule Analytics Engine

Pure-function pipeline. All functions accept `list[ScheduleEvent]` and return data — no database calls, no GUI calls.

```
income_by_job()         →  {canonical_job: IncomeGroup}  sorted by total income desc
daily_totals()          →  {date: income}  for all dates with Work events
date_range_summary()    →  DateRangeSummary  (totals, job groups, date range, work days)
weekly_breakdown()      →  {day_name: income}  for a specific calendar week
top_earning_days(n)     →  [(date, income)]  top-N highest-earning dates
```

---

### Time Engine

Scheduling algorithms, also pure functions:

```
get_free_blocks()       →  list of unscheduled time windows within a configurable day window
detect_conflicts()      →  list of existing events that overlap a new event
weekly_availability()   →  {scheduled_hours, free_hours, availability_pct}
opportunity_cost()      →  potential earnings per job if a free block were filled
```

---

## Database Layer

Five-table SQLite schema with forward-compatible migrations:

```sql
jobs      (id, name UNIQUE, amount, frequency)
expenses  (id, name UNIQUE, amount, category, date, frequency)
settings  (key PK, value)                        -- balance + config key-value store
history   (id, date UNIQUE, balance, income_weekly, expenses_weekly, net_weekly)
events    (id, title, category, day, start_time, end_time, hourly_rate, notes, shift_date)
```

**Schema migration** — `init_db()` inspects live schema using `PRAGMA table_info()` before acting. Old `hourly_rate + hours_per_week` columns are converted to `amount + frequency` automatically. The `shift_date` column is added to existing events tables with a safe default.

**Deduplication** — `dedup_jobs()` and `dedup_expenses()` run on every startup. `SequenceMatcher` clusters entries with similarity ≥ 0.82, keeps the highest-amount row per cluster, renames it to canonical form. `"admissions"`, `"Admissions"`, `"ADMISSIONS"` → one entry.

**Rate propagation** — when a job's hourly rate becomes known, `update_events_rate()` back-fills all matching Work events that had rate=0.

**History snapshots** — `record_snapshot()` is called on every launch, writing today's balance, income, expenses, and net flow to the `history` table. One row per day. Powers the Trends chart passively.

---

## Engineering Decisions

### Canonical name deduplication

`_canon()` was independently defined in four modules — `app.py`, `database.py`, `schedule_analytics.py`, `page_schedule.py`. Any drift between copies would cause job names to stop matching across the sync pipeline, the dedup logic, and analytics grouping: silent data corruption with no error signal.

**Fix:** created `utils.py` with one authoritative `canon_name()`. All four replaced with one-line delegates.

---

### ScenarioEngine projection bug

`extra_weekly` was applied inside a per-job sum loop:

```python
# wrong — extra_weekly multiplied by job count
weekly_income = sum(job.weekly_income() + extra_weekly for job in state.jobs)
```

A user with 3 jobs and `extra_weekly=50` saw `+$150/week` in every forecast. With 5 jobs: `+$250/week`.

```python
# fixed — applied once to total base
base_income   = state.total_income_per_week()
weekly_income = base_income * (1 + raise_percent) + extra_weekly
```

Regression test added. 1-job and 3-job states with identical scenarios must produce results that differ only by base income.

---

### Service layer extraction

60+ lines of schedule-to-financial sync lived in `App.__init__`, untestable without a Tk window. Extracted to `schedule_service.sync_schedule_to_jobs(state)` — pure Python, no GUI dependency, returns `int` count of jobs updated. Now covered by the test suite.

---

### Overnight shift math

`end < start` signals midnight crossing. Without handling this, an 11pm–7am shift returns −16 hours and negative income.

```python
if end <= start:
    end += 1440   # add 24 hours
duration = (end - start) / 60   # → 8.0 hours
```

Covered by a dedicated test case.

---

## Performance

| Operation | Input | Time |
|---|---|---|
| `date_range_summary()` | 2,000 events | ~7ms |
| `shift_impact()` | 1 event + state | ~3 µs |
| Monte Carlo (500 × 52 weeks) | — | < 1 s |
| Full test suite (140+ tests) | — | < 2 s |

---

## Testing

```bash
python3 -m pytest test_fre.py -v
```

140+ tests across 18 test classes. No GUI window required. Database tests use a `tmp_path` fixture that redirects all SQLite connections to a fresh temp file per test — real data is never touched.

| Test Class | Coverage |
|---|---|
| `TestJobModel` | Frequency conversions, dict roundtrip |
| `TestWeeklyTotals` | Income, expenses, net flow, savings rate |
| `TestScores` | Health and risk score at all band boundaries |
| `TestScenarioEngineBugRegression` | `extra_weekly` applied once, not per job |
| `TestScheduleAnalytics` | Income grouping, daily totals, overnight hours |
| `TestShiftImpact` | Income lost, deficit detection, overnight, zero-rate |
| `TestJobEfficiency` | Ranking, early-start flagging, empty input |
| `TestMonteCarlo` | All output keys, probability sum, percentile ordering |
| `TestDatabase` | All CRUD operations against temp file |
| `TestStress` | 2,000-event pipeline: performance + correctness |

---

## Project Structure

```
├── Core
│   ├── financial_state.py      # All financial calculations — single source of truth
│   ├── model.py                # Job + Expense with frequency-aware weekly conversion
│   ├── database.py             # SQLite persistence, migration, backup, dedup
│   ├── utils.py                # canon_name() — shared normalisation
│   └── config.py               # All constants and thresholds
│
├── Engines
│   ├── schedule_analytics.py   # Pure analytics: income by job, shift impact, job efficiency
│   ├── schedule_service.py     # Schedule → financial sync (testable, no GUI)
│   ├── time_engine.py          # Free-block analysis, conflict detection, opportunity cost
│   ├── insight_engine.py       # Score interpretation and insight generation
│   ├── scenario_engine.py      # Side-by-side scenario projection
│   └── simulation.py           # What-If simulator + 500-run Monte Carlo
│
├── Schedule
│   ├── schedule_event.py       # ScheduleEvent dataclass + time helpers
│   ├── schedule_core.py        # Schedule backend — DB ops, week navigation
│   ├── shift_engine.py         # Shift logic engine
│   └── shift_parser.py         # Shift input parsing
│
├── Pages
│   ├── app.py                  # App shell, DI container, navigation, exports
│   ├── page_dashboard.py       # Hero balance, stats, insights
│   ├── page_schedule.py        # Weekly calendar, conflict detection, free time
│   ├── page_analytics.py       # 5-tab analytics with decision engine output
│   ├── page_forecast.py        # Projection, scenario comparison, simulation
│   ├── page_goals.py           # Goal tracking, weeks-to-goal, emergency fund
│   └── page_settings.py
│
├── UI
│   ├── theme.py                # Dark/light palettes, ThemeManager, font constants
│   ├── widgets.py              # ScrollFrame, TabBar, card, kv_row, labeled_entry
│   └── charts.py               # 4 matplotlib chart types embedded in tkinter
│
└── test_fre.py                 # 140+ pytest tests — no GUI instantiation required
```

---

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/financial-reality-engine.git
cd financial-reality-engine
pip install -r requirements.txt
python3 main.py
```

`finance.db` is created on first launch and listed in `.gitignore`.

> **macOS:** if the window appears blank on first launch, run `brew install python-tk`.

---

## Future Work

- **API layer** — expose financial state and analytics as REST endpoints (FastAPI); tkinter becomes one of multiple possible frontends
- **Predictive income modeling** — fit a time-series model to the `history` table; forecast income variance rather than projecting from current averages
- **Recurring event engine** — `repeat_rule` on `ScheduleEvent`; auto-generate future shift instances
- **Real-time impact preview** — surface `shift_impact()` in the Add Event form before the shift is confirmed, not after
- **PostgreSQL migration** — replace `sqlite3` in `database.py` for multi-device sync; no business logic changes required
- **Web or mobile frontend** — once the API layer exists, the analytics and decision engines are already pure functions; binding them to a new UI is straightforward

---

*Built by Aba.*
