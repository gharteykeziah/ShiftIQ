# Engineering Decisions

Why ShiftIQ is built the way it is. For diagrams, see [`Architecture.md`](Architecture.md).

---

## Why Income Is Derived, Not Stored

Most financial apps store income as a number in the database. ShiftIQ derives it from the schedule.

A `Job` record in the database carries `amount` and `frequency` — the face-value amount and how often it is paid. `weekly_income()` converts this using `FREQ_TO_WEEKLY`. But the `amount` itself is populated by `sync_schedule_to_jobs()`, which sums `total_hours × rate` from all matching Work events.

This means:
- Entering a shift automatically updates projected weekly income
- Removing a shift automatically reduces it
- The financial state always reflects the actual schedule, not a manually entered number

The alternative — requiring the user to enter income manually and separately maintain a schedule — creates two sources of truth that will inevitably disagree. ShiftIQ eliminates that class of inconsistency.

## Single Source of Truth for Calculations

`financial_state.py` is the only place financial math is computed. `insight_engine.py`, `scenario_engine.py`, `simulation.py`, `page_analytics.py`, `pdf_report.py`, and the CSV exporter all read from it or accept it as a parameter — none reimplement its logic.

This was an explicit design decision enforced by making financial_state's methods the only path to financial numbers. If a page needs the savings rate, it calls `state.savings_rate()`. It does not compute `net_flow / income` inline. The consequence: there is no possible state where the dashboard shows a different savings rate than the PDF export.

## Pure Functions for Analytics

`schedule_analytics.py` and `time_engine.py` are stateless modules. Their functions take data in, return data out, and touch nothing else. No global state, no database calls, no GUI calls, no `self` references.

This was motivated by testability: to test `income_by_job()`, you create a list of mock `ScheduleEvent` objects and call the function. No database fixture, no window, no app instance. The same function is called from `page_analytics.py`, `pdf_report.py`, and the CSV exporter with identical results.

Pure functions also make the analytics pipeline composable. `date_range_summary()` builds on `income_by_job()` and `daily_totals()`. `job_efficiency_report()` builds on `income_by_job()`. The layers stack cleanly because there are no side effects to manage.

## Dependency Injection Through App

`App(tk.Tk)` owns three objects: `FinancialState`, `ScenarioEngine`, `InsightEngine`. Every page receives `App` as its second constructor argument and accesses state through `self.app.state`, engines through `self.app.scenario_engine`, etc.

No globals. No module-level singleton. No import of `financial_state` from inside a page file. The consequence: replacing `FinancialState` with a different implementation (e.g., one backed by PostgreSQL instead of SQLite) requires changing one line in `app.py`, not hunting through seven page files.

## Validated Mutations with Explicit Return Contracts

Every method that changes data returns `(bool, str)`:

```python
def add_job(self, job: Job) -> tuple[bool, str]:
    ok, reason = self._validate_job(job)
    if not ok:
        return False, reason
    # ... proceed
    return True, f"'{job.name}' added."
```

The UI always knows what happened and has an exact message to display. There are no silent failures and no exceptions that reach the UI layer from a data mutation. This pattern is consistent across `add_job`, `delete_job`, `add_expense`, `delete_expense`, `set_balance`, and `ScheduleEvent.validate()`.

## Schema Migration as a First-Class Concern

`init_db()` inspects the live schema using `PRAGMA table_info()` before deciding what to create or alter. The old schema used `hourly_rate` and `hours_per_week` columns. The migration:

```sql
ALTER TABLE jobs ADD COLUMN amount    REAL
ALTER TABLE jobs ADD COLUMN frequency TEXT DEFAULT 'Weekly'
UPDATE jobs SET amount = hourly_rate * hours_per_week, frequency = 'Weekly'
-- rebuild clean table, copy data, drop old, rename new
```

This runs automatically on first launch. Users who had data in the old format lose nothing. New installs see only the current schema.

The `events` table similarly detects a missing `shift_date` column and adds it with a safe default (`''`), making all existing events legacy-compatible with the date-aware query functions.

This same pattern — inspect, then migrate automatically and idempotently on startup — is what the `fre_jobs`/`fre_shifts` → `schedule_jobs`/`schedule_shifts` table rename in `schedule_core.py` follows as well.

## Name Canonicalization as a Data Integrity Layer

Variable-income workers enter the same job under multiple spellings across sessions. `"Admissions"`, `"admissions"`, `"Admission"`, and `"admissions office"` are all the same job — but a naive string comparison treats them as four distinct records.

ShiftIQ addresses this at three points in the pipeline:

| Stage | Function | Behaviour |
|---|---|---|
| Input | `normalize_job_name()` | Resolves typed name to stored canonical via 4-step lookup |
| Storage | `dedup_jobs()` on startup | Fuzzy-clusters existing rows, merges to highest-amount canonical |
| Analytics | `_canon()` wrapper | Groups income by canonical key so variant spellings aggregate correctly |

All three call the same `canon_name()` function from `utils.py`. Before this was centralised, four independent implementations existed — any one drifting would cause silent grouping failures.

## The shift_date Design Decision

`ScheduleEvent` carries two time-related fields: `day` (weekday name: `"Monday"`) and `shift_date` (ISO date: `"2025-02-10"`).

`day` was the original field, used for display grouping within the week view. `shift_date` was added when the analytics layer required actual calendar dates to compute `daily_totals()`, `weekly_breakdown()`, and `top_earning_days()`.

Separating them allows:
- Backward compatibility: legacy events with no `shift_date` are not broken; they are simply excluded from date-based analytics queries
- Week navigation: `page_schedule.py` navigates by incrementing `week_start` by 7 days, then queries `get_events_for_week(week_start)` which filters by `shift_date >= start AND shift_date <= end`
- Month queries: `get_events_for_month(year, month)` delegates to `get_events_for_date_range()` using the correct month boundaries

## Why 500 Monte Carlo Runs

500 is the convergence point for the probability distribution used here. At 100 runs, `deficit_probability` has high variance between runs of the same simulation. At 500, the standard error on a 15% probability is approximately ±1.7 percentage points — sufficient precision for the decision-support use case. At 1,000, runtime doubles for marginal accuracy gain. The constant lives in `config.MONTE_CARLO_RUNS` and can be adjusted. See [`Performance.md`](Performance.md) for the vectorization benchmark.

## The Frequency Normalisation Contract

Every income and expense amount in the system is normalised to a weekly equivalent before any calculation. The contract is defined in `model.py`:

```python
FREQ_TO_WEEKLY = {
    "Daily":    7.0,
    "Weekly":   1.0,
    "Biweekly": 0.5,
    "Monthly":  12 / 52,   # ≈ 0.2308
}
```

`job.weekly_income()` and `expense.weekly_amount()` both use this table. Nothing else in the codebase does frequency arithmetic — it happens once, in these two methods, using one table. A monthly rent of $1,200 and a daily coffee expense of $5 are both correctly represented in the same weekly unit for net flow and projection calculations.
