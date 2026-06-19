# Aba

**Software engineer focused on systems that model real-world complexity.**

I build tools where the problem is genuinely hard — not because the UI is complex, but because the domain requires careful data modelling, architecture that won't corrupt state, and algorithms that give correct answers on edge cases.

---

## Current Work

**[Financial Reality Engine](https://github.com/YOUR_USERNAME/financial-reality-engine)**

A decision intelligence system for variable-income workers. The core insight: income is not a fixed number for most people — it is `Σ(hours × rate)` across all jobs for the week. FRE models that relationship and answers questions like *"what happens to my financial stability if I drop this shift?"*

The system is ~12,000 lines across 32 Python modules with a layered architecture:

- **Financial State Engine** — single source of truth for all calculations; validated mutations; deterministic risk scoring
- **Decision Engine** — `shift_impact()` computes the financial consequence of removing any shift in ~3µs; `job_efficiency_report()` ranks jobs by $/hr with scheduling friction flags
- **Monte Carlo Simulation** — 500 parallel futures with randomised life events; returns deficit probability over a chosen horizon
- **Schedule Analytics** — pure-function pipeline processing 2,000+ events in ~7ms
- **SQLite persistence** — forward-compatible schema migrations; fuzzy-dedup on startup; passive history snapshots

140+ automated tests. No GUI required to run the test suite. Four production bugs found, documented, fixed, and regression-tested.

---

## What I Care About

**Architecture before features.** A system that does five things correctly is worth more than one that does twenty things unreliably. FRE has one source of truth for financial calculations. The analytics pipeline has no side effects. Name canonicalization has one implementation. These are not accidents — they were deliberate decisions made to prevent specific failure modes.

**Testability as a design constraint.** If a function requires a GUI window or a database connection to test, the architecture is wrong. In FRE, business logic was extracted from the UI layer precisely so the test suite could cover it. The consequence: 140+ tests, zero Tk windows.

**Edge cases as first-class requirements.** Overnight shifts (11pm–7am), variant name spellings, zero-income states, job counts changing projection totals — these are not bugs discovered in QA. They are scenarios that were anticipated, tested, and handled explicitly.

---

## Technical Background

**Languages:** Python (primary), exploring Go for API-layer work

**Systems I think about:** data pipelines, decision-support systems, financial modelling, scheduling algorithms

**Patterns I apply:** pure-function analytics, validated mutations, dependency injection, single-source-of-truth state management, layered architecture

**Currently exploring:** FastAPI for building the API layer behind FRE; PostgreSQL for multi-device data; time-series forecasting to replace the current constant-projection model

---

## Education

Meredith College · Computer Science

---

> "The goal is not to write code that works. It is to write code that cannot be wrong."
