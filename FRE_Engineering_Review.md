# FRE — Senior Engineering Review

**Scope:** Production-hardening for big-tech internship / entry-level SWE quality.
No new features. Only architecture, correctness, maintainability, scalability, and testing.

---

## 1. System Architecture Review

### What is already good

**Pure analytics layer.** `shift_analytics.py` contains zero database calls and zero GUI imports. Every function takes a list and returns a value. This is the hardest architectural discipline to enforce and FRE does it correctly. It means the entire analytics surface is testable without a database or a running app.

**Single source of truth.** `financial_state.py` is the only place that computes income, expenses, risk score, and health score. `InsightEngine` explicitly delegates back to state rather than re-implementing. This is the correct pattern and it holds throughout.

**Clean transport layer.** `api.py` contains zero financial logic. Every endpoint is a one-liner pass-through to an engine module. Adding a new frontend (CLI, React, mobile) requires zero changes to any engine file.

**Config centralization.** Every threshold, path, and constant lives in `config.py`. No magic numbers scattered across files.

**Dependency injection in tests.** `FakeState` in `test_fre.py` mirrors `FinancialState`'s public interface without touching the database. This enables 166 tests with no I/O — the right call.

**Knapsack optimizer.** Correctly implemented, well-commented, includes a regression test that proves it beats the greedy-by-rate heuristic on a constructed counterexample. This is interview-ready code.

---

### What is architecturally weak

The following are real engineering problems — not style preferences.

#### A. `FinancialState.__init__` has a write side effect

```python
# financial_state.py  lines 41–46
def __init__(self) -> None:
    db.init_db()
    self.balance  = db.load_balance()
    self.jobs     = db.load_jobs()
    self.expenses = db.load_expenses()
    # ← HERE: writes to the DB on every instantiation
    db.record_snapshot(
        self.balance,
        self.total_income_per_week(),
        self.total_expense_per_week(),
        self.net_weekly_flow(),
    )
```

`api.py` calls `FinancialState()` on **every HTTP request** via `_get_state()`. This means every `GET /api/state`, `GET /api/jobs`, and `POST /api/optimize/shifts` call writes a snapshot row to the database. The `ON CONFLICT DO UPDATE` makes this idempotent per day, but a constructor should not have write side effects. Constructors load; separate methods mutate.

**Fix:** Move `record_snapshot()` to an explicit `record_daily_snapshot()` method called once per day by the desktop app's startup sequence — not on every instantiation.

#### B. `_shift_hours()` is duplicated in two modules

```python
# optimizer.py  lines 38–49
def _shift_hours(start_time: str, end_time: str) -> float: ...

# shift_analytics.py  lines 33–44
def _shift_hours(event) -> float: ...
```

Same overnight-shift logic, different signatures, no shared implementation. If one gets a bug fix the other doesn't, the optimizer and analytics will silently disagree on shift duration.

**Fix:** Extract to `shift_utils.py` (or add to `schedule_event.py` which already has `to_minutes()`). Both modules import from there.

#### C. `database.py` has two disconnected init functions

```python
db.init_db()           # creates jobs, expenses, settings, history
db.init_events_table() # creates events
```

These are called from different code paths. If any caller calls `get_events()` before `init_events_table()`, they get an `OperationalError: no such table: events`. In `financial_state.py`, `init_db()` is called in `__init__` but `init_events_table()` is called only in schedule-related pages. This is a latent crash waiting for a specific navigation order.

**Fix:** Merge `init_events_table()` into `init_db()`. One init, one call, guaranteed schema.

#### D. `shift_analytics.py` docstring names a module that doesn't exist

```python
# shift_analytics.py  line 2
"""
schedule_analytics.py — Date-range income and schedule analytics for FRE.
```

The file is `shift_analytics.py`. The docstring says `schedule_analytics.py`. Multiple other files (`optimizer.py` line 36, `README.md`) also reference the old name. This tells a reader the module was renamed mid-development without updating callsites — which is exactly what happened, and it's visible.

**Fix:** Update the docstring and every comment reference to match the actual filename.

#### E. `dataclass` imported mid-file in `shift_analytics.py`

```python
# shift_analytics.py  line 264
from dataclasses import dataclass
```

This import is 264 lines into a 386-line file, after multiple function definitions. Imports belong at the top of the file per PEP 8. An interviewer reading this file will notice immediately.

**Fix:** Move `from dataclasses import dataclass` to line 4 with the other imports.

#### F. Two-system income model with no reconciliation

FRE has two parallel income representations:

- **Jobs model** (`financial_state.py`): weekly income from `Job` objects stored in the `jobs` table
- **Schedule model** (`shift_analytics.py`): income computed from `ScheduleEvent` objects in the `events` table

These are never reconciled. A user can have $500/week in Jobs but only $200/week of actual shifts on the schedule. The dashboard shows the Jobs number; the Home page shift strip shows the Schedule number. They disagree silently.

`schedule_service.py` exists to sync them, but this sync is not guaranteed to run and is not tested end-to-end.

This is the most significant architectural gap. It doesn't need a new feature to fix — it needs the documentation to clearly state which number is authoritative and why.

#### G. `ScheduleEvent.validate()` rejects overnight shifts, but `_shift_hours()` handles them

```python
# schedule_event.py  line 101
if end <= start:
    return False, "End time must be after start time."
```

```python
# shift_analytics.py  line 41
if end < start:
    end += 1440  # overnight
```

The analytics layer correctly handles overnight shifts. The data model's own validation rejects them at creation time. Any overnight shift in the database (entered directly or via the import parser) will compute correctly in analytics but would fail the event's own `validate()`. This inconsistency produces wrong test coverage — overnight shift tests in `TestShiftImpact` pass only because the validation is bypassed by direct object construction.

---

## 2. Critical Design Flaws

Ranked by severity:

| # | Flaw | Impact | File |
|---|---|---|---|
| 1 | Constructor write side effect | API reliability, semantic correctness | `financial_state.py` |
| 2 | Two `init_*` functions not guaranteed both called | Latent OperationalError crash | `database.py` |
| 3 | `_shift_hours()` duplicated | Silent divergence between optimizer and analytics | `optimizer.py`, `shift_analytics.py` |
| 4 | Docstring/filename mismatch (`schedule_analytics` vs `shift_analytics`) | Reader confusion, broken import in previous iteration | `shift_analytics.py` and references |
| 5 | Overnight shift validation contradiction | Invalid data can enter DB; validation gives wrong signal | `schedule_event.py` |
| 6 | Mid-file import | PEP 8 violation, readability | `shift_analytics.py` |

---

## 3. Refactored Architecture

### Layered dependency diagram (what depends on what, top to bottom)

```
┌─────────────────────────────────────────────────────────────────┐
│  ENTRY POINTS                                                   │
│  main.py (desktop)          uvicorn api:app (HTTP service)      │
└───────────────────────┬─────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────────┐
│  APPLICATION SHELL                                              │
│  app.py   (DI container, nav, theme)                           │
│  api.py   (FastAPI routes — zero financial logic)               │
└───────────────────────┬─────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────────┐
│  DOMAIN LAYER  (all business logic lives here)                  │
│                                                                 │
│  financial_state.py   ← single source of truth for money data   │
│  scenario_engine.py   ← projection + what-if comparison        │
│  insight_engine.py    ← score interpretation, plain-English     │
│  shift_analytics.py   ← pure schedule analytics, shift_impact  │
│  optimizer.py         ← 0/1 knapsack shift selection           │
│  simulation.py        ← Monte Carlo + what-if simulation        │
│  schedule_service.py  ← schedule→financial sync (side effects) │
└───────────────────────┬─────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────────┐
│  INFRASTRUCTURE LAYER                                           │
│  database.py         ← ALL sqlite3 access, migrations, backup   │
│  activity_log.py     ← append-only activity file               │
└───────────────────────┬─────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────────┐
│  SHARED KERNEL  (imported by any layer above, imports nothing)  │
│  model.py         — Job, Expense dataclasses                   │
│  schedule_event.py — ScheduleEvent dataclass                   │
│  config.py        — all constants and thresholds               │
│  utils.py         — canon_name(), normalize_job_name()          │
│  shift_utils.py   — _shift_hours(), to_minutes() [NEW — merge]  │
└─────────────────────────────────────────────────────────────────┘
```

### Dependency rules (strict)

- Shared Kernel imports **nothing** from this project.
- Infrastructure Layer imports only Shared Kernel.
- Domain Layer imports Infrastructure and Shared Kernel. Domain modules do **not** import each other except: `financial_state` may import `model`; `insight_engine` reads from `financial_state` but does not import it (it accepts `state` as a parameter).
- Application Shell imports Domain + Infrastructure.
- Pages import Application Shell (`app`), Domain (read-only), and Shared Kernel.
- **Nothing** imports `api.py`, `app.py`, or any page module.

---

## 4. File-by-File Improvements

### `financial_state.py`

**1. Remove write side effect from `__init__`.**

Current:
```python
def __init__(self) -> None:
    db.init_db()
    self.balance  = db.load_balance()
    ...
    db.record_snapshot(...)   # ← side effect
```

Fixed:
```python
def __init__(self) -> None:
    db.init_db()
    self.balance  = db.load_balance()
    self.jobs     = db.load_jobs()
    self.expenses = db.load_expenses()
    logger.info("FinancialState initialised — %d jobs, %d expenses, balance $%.2f",
                len(self.jobs), len(self.expenses), self.balance)

def record_daily_snapshot(self) -> None:
    """Call once per app session, not once per instantiation."""
    db.record_snapshot(
        self.balance,
        self.total_income_per_week(),
        self.total_expense_per_week(),
        self.net_weekly_flow(),
    )
```

Call `state.record_daily_snapshot()` in `main.py` after the first app startup, not in `__init__`.

**2. Replace the `weeks_to_goal` while-loop with a formula.**

Current: O(N) while loop, up to 10,000 iterations.
```python
def weeks_to_goal(self, goal_amount: float) -> int | None:
    if self.net_weekly_flow() <= 0:
        return None
    weeks, balance = 0, self.balance
    while balance < goal_amount:
        balance += self.net_weekly_flow()
        weeks   += 1
        if weeks > 10_000:
            return None
    return weeks
```

Fixed: O(1).
```python
import math

def weeks_to_goal(self, goal_amount: float) -> int | None:
    net = self.net_weekly_flow()
    if net <= 0:
        return None
    remaining = goal_amount - self.balance
    if remaining <= 0:
        return 0
    weeks = math.ceil(remaining / net)
    return weeks if weeks <= 10_000 else None
```

**3. Move `logging.basicConfig` out of module-level code.**
Calling `logging.basicConfig` at import time hijacks the root logger for any process that imports `financial_state.py` — including pytest. Move it to `main.py` so it only applies to the running desktop app, not to tests or the API server.

**4. Extract validation to `model.py`.**
`_validate_job` and `_validate_expense` are static methods on `FinancialState` but they only inspect the model objects. They belong on `Job` and `Expense` directly:
```python
class Job:
    def validate(self) -> tuple[bool, str]:
        if not self.name or not self.name.strip():
            return False, "Name cannot be blank."
        if self.amount <= 0:
            return False, "Amount must be greater than zero."
        if self.frequency not in FREQUENCIES:
            return False, f"Frequency must be one of: {', '.join(FREQUENCIES)}."
        return True, ""
```

---

### `database.py`

**1. Merge `init_events_table()` into `init_db()`.**
There should be exactly one function that sets up the schema. Any caller that calls any database function can rely on calling `init_db()` once and getting a fully ready schema.

**2. Move `import datetime` and `import calendar` to the top of the file.**
Both are imported lazily inside functions (`record_snapshot`, `get_events_for_month`). These are stdlib modules — there is no cost to importing them at the top, and it makes the file's dependencies immediately visible.

**3. Comment the f-string SQL in `update_event()`.**
```python
cols = ", ".join(f"{k} = ?" for k in updates)
vals = list(updates.values()) + [event_id]
with sqlite3.connect(DB_NAME) as conn:
    conn.execute(f"UPDATE events SET {cols} WHERE id = ?", vals)
```
This is safe (fields are whitelist-filtered on line above) but looks like a SQL injection risk at first glance. Add a one-line comment: `# safe: only whitelisted column names are substituted`.

**4. Consider a `get_connection()` context manager for the API layer.**
Each DB function opens its own connection. For the desktop app this is fine. For the FastAPI layer, a single request to `POST /api/optimize/shifts` opens three connections in sequence (one per function call). Extract:
```python
from contextlib import contextmanager

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_NAME)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```
This also makes transaction grouping explicit when needed.

---

### `shift_analytics.py`

**1. Fix the module docstring.** Line 2: `schedule_analytics.py` → `shift_analytics.py`.

**2. Move `from dataclasses import dataclass` to line 4.**

**3. Remove `_canon()` wrapper.** It's a one-line wrapper around `canon_name`. Callers should just call `canon_name()` directly — the wrapper adds indirection without adding semantics.

**4. Remove the duplicated `_shift_hours()` and import from `shift_utils`.** (See below.)

---

### `optimizer.py`

**1. Fix the comment on line 36.** `schedule_analytics.py` → `shift_analytics.py`.

**2. Remove the duplicated `_shift_hours()` and import from `shift_utils`.**

---

### `schedule_event.py`

**1. Fix the overnight shift contradiction.**
Either:
- Update `validate()` to allow overnight shifts: `if end == start: return False, "Zero-duration shift."` (removes the `end < start` rejection), OR
- Add explicit overnight-shift handling to `duration_hours()` to match `_shift_hours()`.

The analytics layer handles overnight shifts correctly. The data model should match.

---

### `insight_engine.py` and `scenario_engine.py`

Both classes have no instance state — `InsightEngine.__init__` doesn't exist, `ScenarioEngine.__init__` doesn't exist. A class with no state is a module. Converting them to plain functions reduces indirection:

```python
# insight_engine.py  becomes a module with functions
def risk_label(score: int) -> str: ...
def health_label(score: int) -> str: ...
def generate_insights(state, simulation_results=None) -> list[str]: ...
```

This is a non-breaking change (callers update to `insight_engine.risk_label(score)` instead of `ie.risk_label(score)`).

If maintaining class structure for DI reasons, keep them as classes — but document why.

---

### `model.py`

**1. Convert `Job` and `Expense` to `@dataclass`.**
Plain classes in Python get no `__eq__` by default. `any(j.name == job.name for j in self.jobs)` in `financial_state.py` is correct but only because name comparison is used explicitly everywhere. If anyone ever compares two `Job` objects directly (`job_a == job_b`), they get identity comparison, not value comparison — a silent bug.

```python
from dataclasses import dataclass

@dataclass
class Job:
    name:      str
    amount:    float
    frequency: str = "Weekly"

    def weekly_income(self) -> float:
        return self.amount * FREQ_TO_WEEKLY.get(self.frequency, 1.0)
```

`to_dict` / `from_dict` can use `dataclasses.asdict` or stay manual.

**2. Validate `frequency` in `__post_init__`** if using dataclasses, so invalid Jobs can't be constructed at all.

---

### `simulation.py`

**1. Remove `activity_log` from the Monte Carlo engine.**
`run_monte_carlo()` calls `activity_log.log(...)` as a side effect. This makes the function non-pure and untestable in isolation. The engine should return results; the caller decides whether to log.

Same applies to `simulate_whatif()`. Move the `activity_log.log()` calls to `page_forecast.py` (the caller), not the engine.

**2. Use NumPy for the deficit count** (already have the array in memory):
```python
# Current — converts back to Python list then iterates
deficit_count = sum(1 for b in ending_balances if b < 0)

# Better — stay in NumPy
deficit_count = int(np.sum(ending_balances_arr < 0))
```

**3. Add `seed` parameter for reproducible tests:**
```python
def run_monte_carlo(state, weeks: int, n: int = MONTE_CARLO_RUNS,
                    seed: int | None = None) -> dict:
    if seed is not None:
        np.random.seed(seed)
    ...
```
This enables deterministic tests (`assert result["average"] == expected`) instead of only statistical range checks.

---

### `utils.py`

**1. Move the fuzzy threshold `0.82` to `config.py`.**
It appears hardcoded in three places: `utils.normalize_job_name()`, `database._fuzzy_group()`, and `database.update_events_rate()`. One constant, three values — they can drift.

```python
# config.py
FUZZY_MATCH_THRESHOLD = 0.82
```

---

## 5. Clean Dependency Flow

### Current (actual imports, traced from code)

```
financial_state ──→ database, model, activity_log, config, utils
shift_analytics ──→ utils                             [GOOD — pure]
optimizer       ──→ (nothing from project)             [GOOD — pure]
simulation      ──→ activity_log, config, numpy        [BAD — side effect]
insight_engine  ──→ config
scenario_engine ──→ (nothing)
database        ──→ model, config, utils, schedule_event (lazy)
api.py          ──→ database, financial_state, insight_engine,
                    simulation, optimizer, shift_analytics, model, config
app.py          ──→ theme, activity_log, database, pdf_report,
                    financial_state, scenario_engine, insight_engine,
                    config, utils, schedule_service
```

### Target (after refactor)

```
Shared Kernel:   model, schedule_event, config, utils, shift_utils
                 → no project imports

Infrastructure:  database, activity_log
                 → imports only Shared Kernel

Domain:          financial_state  → database, model, config, utils
                 shift_analytics  → utils, shift_utils         [pure]
                 optimizer        → shift_utils                [pure]
                 simulation       → config, numpy              [pure — no activity_log]
                 insight_engine   → config                     [pure]
                 scenario_engine  → (nothing)                  [pure]
                 schedule_service → database, financial_state, shift_analytics

Application:     api.py  → domain modules only (no database directly)
                 app.py  → domain + infrastructure
```

The key improvement: `simulation.py` and `shift_analytics.py` become truly pure — no I/O, no side effects. An interviewer can look at either file and verify correctness by reading it alone.

---

## 6. Testing Strategy for Big-Tech Level Quality

### Current test pyramid

```
166 unit tests  (strong)
0 integration tests
0 end-to-end tests
0 property-based tests
```

### Target pyramid

```
~166 unit tests    (keep — they're good)
~15 integration tests
~5 end-to-end / contract tests
~10 property-based tests (hypothesis)
```

### Specific additions (no new features required)

**Integration tests for the API layer** (`tests/test_api.py`):
```python
from fastapi.testclient import TestClient
from api import app

client = TestClient(app)

def test_health_endpoint():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

def test_state_endpoint_returns_required_keys():
    r = client.get("/api/state")
    assert r.status_code == 200
    for key in ("balance", "weekly_income", "net_weekly_flow", "risk_score"):
        assert key in r.json()

def test_optimize_shifts_respects_budget():
    r = client.post("/api/optimize/shifts", json={"max_hours": 20})
    assert r.status_code == 200
    assert r.json()["total_hours"] <= 20
```

**Property-based tests for the optimizer** (using `hypothesis`):
```python
from hypothesis import given, strategies as st
from optimizer import ShiftCandidate, optimize_shift_selection

@given(
    shifts=st.lists(
        st.builds(ShiftCandidate,
            id=st.text(min_size=1),
            job_name=st.text(min_size=1),
            hours=st.floats(min_value=0.25, max_value=12.0),
            hourly_rate=st.floats(min_value=7.25, max_value=100.0)
        ),
        min_size=0, max_size=20
    ),
    budget=st.floats(min_value=0.25, max_value=80.0)
)
def test_optimizer_never_exceeds_budget(shifts, budget):
    result = optimize_shift_selection(shifts, budget)
    assert result.total_hours <= budget + 0.01  # quarter-hour rounding tolerance
```

This catches edge cases — fractional hours, zero-rate shifts, empty candidates — without you having to enumerate them manually.

**Deterministic Monte Carlo tests** (once seed parameter is added):
```python
def test_monte_carlo_deterministic_with_seed():
    state = FakeState(jobs=[Job("Job A", 500, "Weekly")],
                      expenses=[Expense("Rent", 300, "Housing", "2024-01-01", "Monthly")],
                      balance=1000.0)
    r1 = run_monte_carlo(state, weeks=12, n=100, seed=42)
    r2 = run_monte_carlo(state, weeks=12, n=100, seed=42)
    assert r1["average"] == r2["average"]
    assert r1["deficit_probability"] == r2["deficit_probability"]
```

**FakeState divergence guard:**
`FakeState` in `test_fre.py` duplicates `FinancialState`'s calculation logic. Add a test that verifies they agree:

```python
def test_fake_state_matches_real_state_calculations(tmp_path):
    """FakeState and FinancialState must produce identical results for
    the same input so test coverage isn't silently misleading."""
    jobs     = [Job("Job A", 500, "Weekly")]
    expenses = [Expense("Rent", 1200, "Housing", "2024-01-01", "Monthly")]
    fake     = FakeState(jobs=jobs, expenses=expenses, balance=500.0)
    # instantiate FinancialState with the same data via a temp DB
    ...
    assert fake.net_weekly_flow() == real.net_weekly_flow()
    assert fake.savings_rate()    == real.savings_rate()
```

**Test file organization.** The current single `test_fre.py` (1200+ lines) works but makes it hard to run one subsystem's tests quickly. At Google/Amazon scale, the convention is:

```
tests/
  unit/
    test_model.py
    test_financial_state.py
    test_shift_analytics.py
    test_optimizer.py
    test_simulation.py
    test_scenario_engine.py
    test_database.py
  integration/
    test_api.py
    test_schedule_service.py
  property/
    test_optimizer_properties.py
```

The existing tests map cleanly to this structure — it's a rename/move, not a rewrite.

---

## 7. Performance + Scalability Improvements

### Already fast (don't change)

- Monte Carlo vectorization: correct and benchmarked. The `_EVENT_PROB`, `_EVENT_MIN`, `_EVENT_MAX` arrays are hoisted to module-level constants — exactly right.
- Knapsack: O(n × capacity) — optimal for exact DP.
- SQLite with context managers: appropriate for single-user embedded persistence.

### Improvements worth making

**1. Cache `FinancialState` reads in the API layer.**
Currently, three sequential API calls to `/api/state`, `/api/jobs`, and `/api/analytics/income` each open 2–3 SQLite connections and reload all jobs/expenses from scratch. At the scale of a single user this is fine, but it's not the pattern you'd describe in an interview.

Add a per-request state cache with a 1-second TTL — cheap and shows the concept:
```python
import time
from functools import lru_cache

_state_cache: tuple[float, FinancialState] | None = None
_CACHE_TTL = 1.0  # seconds

def _get_state() -> FinancialState:
    global _state_cache
    now = time.monotonic()
    if _state_cache is None or now - _state_cache[0] > _CACHE_TTL:
        _state_cache = (now, FinancialState())
    return _state_cache[1]
```

**2. Add a DB index on `events.shift_date`.**
`get_events_for_week()` and `get_events_for_date_range()` do a full table scan filtered by `shift_date`. As the events table grows over years of use, these queries slow down linearly. One index fixes this permanently:

```sql
CREATE INDEX IF NOT EXISTS idx_events_shift_date ON events(shift_date);
```

Add this to `init_db()`.

**3. Eliminate the `sum(1 for b in ending_balances if b < 0)` loop** — already have a NumPy array at that point:
```python
# Current
deficit_count = sum(1 for b in ending_balances if b < 0)  # Python loop on converted list

# Better
deficit_count = int(np.sum(ending_balances_arr < 0))  # vectorized, stays in NumPy
```

**4. `weeks_to_goal()` O(1) formula** — covered above in `financial_state.py` section. The current while loop runs up to 10,000 iterations for a goal far in the future.

**5. `dedup_jobs()` is O(n²) fuzzy matching.** `_fuzzy_group()` compares every row against every cluster — O(n²) in the number of jobs. For a student with 3–5 jobs this is invisible. But it's worth noting: the correct pattern is to normalize keys before insertion (which `canon_name()` does) and enforce uniqueness at the DB level (which `UNIQUE` on `name` does). The `_fuzzy_group()` path only runs for legacy data with inconsistent names. It's fine — just not scalable.

---

## Summary: Priority Order for Implementation

| Priority | Change | Files | Effort |
|---|---|---|---|
| P0 | Fix `__init__` write side effect | `financial_state.py`, `main.py` | 15 min |
| P0 | Merge `init_events_table()` into `init_db()` | `database.py`, callers | 10 min |
| P0 | Fix docstring naming (`schedule_analytics` → `shift_analytics`) | `shift_analytics.py`, comments | 5 min |
| P0 | Move mid-file import to top | `shift_analytics.py` | 1 min |
| P1 | Extract `_shift_hours()` to shared utility | new `shift_utils.py`, 2 callers | 20 min |
| P1 | Fix overnight shift contradiction in `validate()` | `schedule_event.py` | 10 min |
| P1 | `weeks_to_goal()` O(1) formula | `financial_state.py` | 5 min |
| P1 | Remove `activity_log` from `simulation.py` | `simulation.py`, page callers | 15 min |
| P1 | Add DB index on `shift_date` | `database.py` | 2 min |
| P2 | Add `seed` param to `run_monte_carlo` | `simulation.py`, tests | 10 min |
| P2 | Move `logging.basicConfig` to `main.py` | `financial_state.py`, `main.py` | 5 min |
| P2 | `FUZZY_MATCH_THRESHOLD` constant in `config.py` | `config.py`, 3 callers | 10 min |
| P2 | Convert `Job` / `Expense` to dataclasses | `model.py`, tests | 30 min |
| P2 | API integration tests | new `tests/test_api.py` | 45 min |
| P3 | Property-based tests for optimizer | new test file | 30 min |
| P3 | Split `test_fre.py` into test directory | test files | 30 min |

P0 items are correctness/clarity fixes with no behavior change.
P1 items improve robustness and remove latent bugs.
P2 and P3 items improve long-term maintainability and test coverage.
