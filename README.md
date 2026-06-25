# ShiftIQ

[![Tests](https://github.com/gharteykeziah-hub/shiftiq/actions/workflows/tests.yml/badge.svg)](https://github.com/gharteykeziah-hub/shiftiq/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

When income depends on time rather than a fixed salary, the standard model of financial software breaks down. There is no meaningful budget when the variable being budgeted against is itself a function of decisions not yet made.

ShiftIQ is a decision system built for this class of problem. Income is treated as a derived quantity, not an input:

```
Income = Σ (shift hours × hourly rate)
```

The system takes a schedule as input and propagates it through a full state model in real time. Change a shift and weekly income, net flow, savings rate, risk score, and 52-week balance projection all update immediately. The core decision interface is `shift_impact()`, running in ~3 µs, which answers one question before any schedule change is committed: what does this cost? Behind it, a Monte Carlo engine runs 500 independent trajectories over a configurable horizon to quantify the uncertainty in that answer.

---

## Architecture

The design enforces three constraints that hold across the entire codebase: the analytics layer is stateless and pure, the state layer is the single source of truth for all derived quantities, and both frontends are zero-logic transport layers over the same unmodified engine.

```
Schedule
    ↓
Analytics Layer       shift_impact() · efficiency ranking · income aggregation
    ↓                 pure functions, no DB access, no UI imports
State Layer           net flow · savings rate · risk score · balance projection
    ↓                 single source of truth, no module recomputes these
Decision Engines      what-if · scenario comparison · Monte Carlo (500 x 52 weeks)
    ↓
┌────────────────────────────┬─────────────────────────────┐
│  Desktop UI                │  FastAPI + Pydantic v2      │
│  Home · Schedule · More    │  Swagger docs at /docs      │
└────────────────────────────┴─────────────────────────────┘
```

Because both frontends are thin transport layers, adding a third (CLI, React, mobile) requires zero changes to any engine module. Every number either frontend surfaces comes from the same code path.

---

## Shift Optimizer

Selecting shifts greedily by hourly rate is provably suboptimal under an hour budget. A lower-rate short shift that leaves capacity for two others can produce greater total value than a higher-rate long shift that saturates the constraint. This is a 0/1 knapsack problem where items have weight (hours) and value (income) and fractional selection is not permitted.

`optimizer.py` solves it exactly via dynamic programming at O(n × capacity), discretized to quarter-hour units:

```python
candidates = [
    ShiftCandidate("x", "Job X", hours=9, hourly_rate=20),  # $180, highest rate
    ShiftCandidate("y", "Job Y", hours=5, hourly_rate=19),  # $95
    ShiftCandidate("z", "Job Z", hours=5, hourly_rate=19),  # $95
]
result = optimize_shift_selection(candidates, max_hours=10)
# greedy picks X alone:   $180
# knapsack picks Y + Z:   $190  <- provably optimal
```

The test suite includes a dedicated regression test that asserts the DP solution outperforms greedy on this exact counterexample.

---

## Monte Carlo Simulation

A point estimate of future balance ignores the variance inherent in schedule-dependent income. The simulation runs 500 independent trajectories over a configurable horizon, sampling 10 stochastic weekly events per run that represent the real variability in shift-based work: hours cut, tips lost, extra shifts picked up, unexpected expenses. The result is a distribution over outcomes, not a single projection.

The original implementation nested Python loops across runs, weeks, and events. The current version draws all random values in a single batched NumPy call and applies boolean masks across the full array at once:

| Scenario | Pure Python | Vectorized | Speedup |
|---|---|---|---|
| 500 runs / 52 weeks | 27.7 ms | 5.5 ms | **5.0x** |
| 500 runs / 12 weeks | 6.5 ms | 1.7 ms | 3.8x |
| 5,000 runs / 52 weeks | 282.2 ms | 44.8 ms | **6.3x** |

Reproduce: `python3 scripts/benchmark_monte_carlo.py`

---

## Testing

166 pytest tests across 19 classes with no GUI instantiation and no live database. This is a direct consequence of the architecture: because the analytics layer is pure and the state layer has no UI dependencies, a `FakeState` protocol mirroring the state layer's public interface is sufficient for full calculation coverage in isolation. The test suite covers the knapsack optimizer including the greedy counterexample regression, Monte Carlo output stability, overnight shift edge cases, and database integrity.

```bash
python3 -m pytest test_fre.py -v
```

GitHub Actions runs the full suite on every push across Python 3.10, 3.11, and 3.12.

---

## Project Structure

```
├── financial_state.py      # State layer, single source of truth for all derived quantities
├── shift_analytics.py      # Pure analytics: income aggregation, shift impact, efficiency
├── optimizer.py            # 0/1 knapsack shift-selection, O(n x capacity)
├── simulation.py           # NumPy-vectorized Monte Carlo + what-if simulator
├── insight_engine.py       # Score interpretation and output labeling
├── scenario_engine.py      # Side-by-side scenario projection
├── database.py             # SQLite persistence, migration, backup, dedup
├── model.py                # Core data models with frequency-aware rate conversion
├── schedule_service.py     # Schedule to state sync
├── api.py                  # FastAPI service, zero-logic transport over engine
├── app.py                  # Desktop app shell, DI container, 3-item nav
├── page_home.py            # Home: shift strip, tap-impact cards, optimizer
├── test_fre.py             # 166 tests, no GUI or DB required
└── scripts/
    └── benchmark_monte_carlo.py
```

---

## Stack

Python 3.10+, SQLite, NumPy, matplotlib, reportlab, pytest, FastAPI, Pydantic v2. No ORM. No frontend build step. The API layer is opt-in and adds zero dependencies to the desktop app.

---

## Quick Start

```bash
git clone https://github.com/gharteykeziah-hub/shiftiq.git
cd shiftiq
pip install -r requirements.txt
python3 main.py
```

> **macOS:** if the window appears blank on first launch, run `brew install python-tk`.

To also run the API service:

```bash
pip install -r requirements-api.txt
uvicorn api:app --reload
# http://127.0.0.1:8000       -> browser frontend
# http://127.0.0.1:8000/docs  -> Swagger docs
```

`render.yaml` is included for one-command deployment to Render, Railway, or Heroku.
