# Internship Positioning — Google / Amazon SWE

This document contains positioning copy calibrated for Google and Amazon SWE internship applications: resume bullet points, project descriptions, behavioral story frameworks, and system design talking points. All claims are grounded in the actual codebase.

---

## Resume Bullet Points

Use these in the Projects section. Each bullet leads with a result, not a technology.

**Option A — Architecture focus**
> Designed and built a modular financial decision system in Python with a layered architecture (persistence, business logic, analytics, UI), 140+ automated tests, and a Monte Carlo simulation engine that models deficit probability across 500 randomised financial futures.

**Option B — Decision engine focus**
> Built a real-time decision engine (`shift_impact`) that computes the financial consequence of any schedule change in ~3 microseconds; identified and fixed a projection bug that was silently inflating multi-job forecasts by 2–5×.

**Option C — Scale and correctness focus**
> Implemented a pure-function analytics pipeline processing 2,000+ schedule events in ~7ms with canonical name deduplication (SequenceMatcher ≥ 0.82 threshold) that prevents data corruption from variant spellings across 32 interacting modules.

**Option D — Full scope**
> Financial Reality Engine: ~12,000 lines, 32 modules, 140+ tests. Built the financial state engine (single source of truth for all calculations), schedule analytics pipeline (pure functions, no GUI dependency), SQLite persistence layer with automatic schema migration, and a 500-run Monte Carlo simulation. Found and regression-tested 4 production-level bugs.

---

## Project Description (for application forms, 150 words)

Financial Reality Engine is a decision intelligence system that models the relationship between time allocation and financial stability for people with variable income — gig workers, shift employees, hourly contractors.

The system derives income from a scheduling engine rather than treating it as a fixed input. A scheduled Work event (title, hours, rate) flows through a canonicalization pipeline into a financial state engine that computes weekly income, net flow, savings rate, and a multi-factor risk score. A Monte Carlo module runs 500 parallel financial futures to estimate deficit probability over a chosen horizon.

The architecture enforces strict layer separation: analytics are pure functions (testable without a database), business logic is extracted from the UI (testable without a window), and all financial calculations live in a single module with no duplication. The 140+ test suite covers financial calculations, schedule analytics, the simulation engine, and database operations using a temp-file fixture that never touches real data.

---

## Project Description (for application forms, 75 words)

Financial Reality Engine: a modular Python system modeling the time-to-income relationship for variable-income workers. Income is derived from scheduled shifts, not manually entered. Architecture: persistent SQLite layer with schema migration and fuzzy deduplication, financial state engine as single source of truth, pure-function analytics pipeline, Monte Carlo simulation (500 runs), decision engine computing shift-removal impact in ~3µs. 140+ automated tests, zero GUI dependency in the test suite. ~12,000 lines, 32 modules.

---

## Behavioral Story Frameworks (STAR Format)

### "Tell me about a bug you found and fixed."

**Situation:** Working on the scenario projection feature of FRE, a financial decision system I built.

**Task:** Verify that the What-If scenario engine correctly projected balance changes for different income configurations.

**Action:** I wrote a test with three different job counts and identical extra_weekly income values. The test failed — a user with 3 jobs was seeing 3× the projected extra income compared to a user with 1 job. I traced it to the projection loop: `extra_weekly` was being applied once per job inside the sum, not once to the total. The formula was: `sum(job.weekly_income() + extra_weekly for job in state.jobs)`. With 3 jobs and extra_weekly=50, this produced +$150/week instead of +$50/week — every multi-job forecast was silently wrong. I fixed it by computing `base_income = state.total_income_per_week()` first, then `weekly_income = base_income * (1 + raise_percent) + extra_weekly`. I added a regression test that explicitly asserts 1-job and 3-job states with the same scenario produce results differing only by base income.

**Result:** The bug was caught, fixed, and cannot regress. Anyone who had used the scenario tool with multiple jobs had been receiving inflated projections — the kind of silent error that erodes trust in a financial tool.

---

### "Tell me about a design decision you made and why."

**Situation:** The analytics pipeline in FRE needed to produce income summaries, daily totals, job efficiency rankings, and shift impact calculations.

**Task:** Decide where this logic lived and how it connected to the rest of the system.

**Action:** I made `schedule_analytics.py` a pure-function module — every function accepts a list of events and returns a data structure. No database calls, no GUI references, no global state. This was a deliberate constraint. The consequence: I can test `income_by_job()` by creating a list of mock events in the test file and calling the function directly. No database fixture, no app instance, no Tk window. The same function is called from the analytics page, the PDF export, and the CSV export — three different consumers, one implementation, consistent results.

**Result:** The analytics layer has full test coverage including a 2,000-event stress test that asserts correctness and performance (<1s). The PDF and CSV exports produce identical analytics because they call the same function. Adding a new consumer — say, an API endpoint — requires zero changes to the analytics module.

---

### "Tell me about a time you improved code quality or maintainability."

**Situation:** During an audit of FRE's codebase, I found that `_canon()` — the function that normalises job names to a canonical form — was independently defined in four different files: `app.py`, `database.py`, `schedule_analytics.py`, and `page_schedule.py`.

**Task:** The copies were identical at that moment, but any future change to the normalisation logic would require finding and updating all four. More critically, if one copy drifted, job names would stop matching across the income sync pipeline, the analytics grouping, and the database deduplication — silent data corruption with no error signal.

**Action:** I created `utils.py` with one authoritative `canon_name()` function. I replaced all four independent definitions with single-line imports and delegates. I added a test class (`TestCanonName`) covering idempotency, case variants, short-name preservation, whitespace handling, and consistency across all calling sites.

**Result:** One function, one definition, one set of tests. The duplication-based failure mode is structurally eliminated — you cannot have drift because there is nothing to drift against.

---

### "Tell me about a complex system you designed."

*(Use this for design rounds or "walk me through a project" prompts)*

**Opening:** I built a financial decision system called FRE that models the relationship between time allocation and income for variable-income workers. The central problem is that most financial software treats income as a fixed input. For the target users — gig workers, shift employees, freelancers — income is a function: it changes based on what shifts are accepted and at what rates.

**Architecture:** The system has five layers. The persistence layer is SQLite with schema migration and fuzzy deduplication. The business logic layer is a single `FinancialState` class that owns all calculations — nothing else in the system recalculates weekly income or risk score. The analytics layer is pure functions that accept event lists and return data structures, with no side effects. The simulation layer runs 500 Monte Carlo futures. The UI layer is tkinter, with all business logic extracted out so it can be tested independently.

**Key decisions I'd highlight:**

1. *Deriving income from schedule data instead of storing it directly* — eliminates the class of inconsistency where manually entered income disagrees with the schedule
2. *Pure-function analytics* — made the entire analytics pipeline unit-testable without infrastructure
3. *Validated mutations returning (bool, str)* — every state change has an explicit success/failure contract; no exceptions reach the UI

**Interesting problems I solved:** Canonical name normalisation across four modules that were maintaining independent copies. Projection bugs where extra income was applied once per job rather than once per scenario. Schema migration that preserves data from an old column structure. Overnight shift math where end < start requires adding 1,440 minutes to get a positive duration.

---

## System Design Talking Points

If asked to explain FRE in a system design context:

**On data flow:**
"The system has a single write path for financial numbers: schedule events → sync service → jobs table → FinancialState. Every read path — dashboard, PDF, CSV, analytics — reads from the same FinancialState object. There is no way for two UI surfaces to show different weekly income values."

**On testing strategy:**
"I designed the business logic layer to have no UI or database dependency so I could test it directly. The test suite has 140+ tests and runs in under 2 seconds. The database tests use a temp-file fixture that redirects all SQLite connections to a fresh file per test — the real database is never touched."

**On scalability limitations (honest answer):**
"SQLite is single-writer. This works perfectly for a single-user desktop app, but it rules out concurrent access or a web deployment without replacing the persistence layer. The architecture is designed to make that migration straightforward: `database.py` is the only module with SQLite calls. Replacing it with PostgreSQL requires changing one file, not hunting through the codebase."

**On what I'd do differently:**
"I'd add a REST API layer earlier. Right now the analytics and decision engine are pure Python functions — binding them to API endpoints would be straightforward, and it would enable a mobile frontend. I also built the week navigation system before adding the `shift_date` field, which created a compatibility layer between logical weekdays and actual calendar dates that adds some complexity."

---

## One-Paragraph Positioning Statement

*(For cover letters or "about me" sections)*

I build systems where architecture decisions have direct consequences on correctness. My current project, Financial Reality Engine, is a decision intelligence system that models time-to-income relationships for variable-income workers. Working on it taught me that the most important bugs are the silent ones — the projection error that inflated every multi-job forecast, the duplicated canonicalization function that would have caused data corruption on any future change, the analytics module that couldn't be tested because it was entangled with the UI layer. I spent as much time on the architecture that prevents these problems as on the features themselves: single source of truth for calculations, pure-function analytics, validated mutations, explicit test coverage of edge cases. That approach — treating correctness as a structural property rather than a testing afterthought — is what I want to bring to a team working on systems that matter.
