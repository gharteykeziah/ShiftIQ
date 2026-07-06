# Algorithms

The four algorithmic pieces that do the actual decision-support work. Benchmark numbers live in [`Performance.md`](Performance.md); design rationale lives in [`Engineering-Decisions.md`](Engineering-Decisions.md).

---

## Shift Optimizer — 0/1 Knapsack

**File:** `optimizer.py`

`job_efficiency_report()` (in `shift_analytics.py`) ranks jobs by effective $/hr, but sorting doesn't answer the question a variable-income worker actually has:

> "I only have 25 hours free this week. Which combination of available shifts should I take to earn the most?"

Taking the highest-rate shifts first is not guaranteed optimal once an hour budget constrains which shifts can coexist — a worse-paying short shift can unlock a better total than a better-paying long one that consumes the whole budget:

```python
candidates = [
    ShiftCandidate("x", "Job X", hours=9, hourly_rate=20),  # $180
    ShiftCandidate("y", "Job Y", hours=5, hourly_rate=19),  # $95
    ShiftCandidate("z", "Job Z", hours=5, hourly_rate=19),  # $95
]
optimize_shift_selection(candidates, max_hours=10)
# greedy picks X alone:   $180
# knapsack picks Y + Z:   $190  <- provably optimal
```

This is the classic 0/1 knapsack problem: each shift is an item with a weight (hours) and a value (income); the hour budget is the knapsack capacity. `optimize_shift_selection()` solves it exactly with dynamic programming:

- Hours are discretized to quarter-hour units (`_QUANTUM_PER_HOUR = 4`) to keep the DP table size bounded and match ShiftIQ's scheduling grid.
- `dp[i][w]` = best achievable income using the first `i` candidates with total weight ≤ `w` quarter-hours.
- Runs in **O(n × capacity)** time and space, where `capacity = max_hours × 4`.
- Selection is reconstructed by walking the DP table backward from `dp[n][capacity]`, checking `dp[i][w] != dp[i-1][w]` to decide whether candidate `i` was taken.
- Deterministic: the same input always produces the same selection.

`candidates_from_events()` adapts real `ScheduleEvent` rows into `ShiftCandidate` objects, skipping non-Work events and any shift with no rate set.

## Monte Carlo Simulation

**File:** `simulation.py`

`run_monte_carlo(state, weeks, n=500)` models the user's next N weeks under everyday financial randomness — missed shifts, surprise bills, extra tips — rather than assuming the current weekly flow holds exactly.

**Event model.** Ten background events (`_RANDOM_EVENTS`), each with an independent probability and a dollar range, e.g. `"Extra shift"` (15% chance, +$50 to +$200) or `"Car repair"` (6% chance, –$400 to –$80). Every event rolls independently, every week, in every simulated run.

**Vectorization.** The original implementation nested Python loops across runs, weeks, and events — `n × weeks × 10` individual dice rolls. The current version:

1. Hoists event parameters (`_EVENT_PROB`, `_EVENT_MIN`, `_EVENT_MAX`) into NumPy arrays once, at import time.
2. Draws all `(n, weeks, num_events)` Bernoulli "did this event hit" outcomes in a single `np.random.random()` call.
3. Draws magnitudes for every event slot regardless of hit/miss (cheaper than conditional drawing, statistically identical since misses are masked to zero).
4. Multiplies hits × magnitudes and sums over the event axis to get an `(n, weeks)` array of weekly random totals.
5. Adds `weekly_flow * weeks` and the initial balance to get `n` ending balances in one vectorized pass.

Same statistical model as the original nested-loop version — every event still rolls independently per week with the same probability and range — just computed with array operations instead of `n * weeks` individual Python-level draws. See [`Performance.md`](Performance.md) for the resulting speedup.

**Output.** Average, best case, worst case, median, p25/p75 percentiles, and a deficit probability (`% of runs ending below zero`), plus a plain-English risk sentence generated from thresholds on that probability.

A second, simpler simulation — `simulate_whatif(state, description, dollar_change, weeks)` — projects a single user-described event (e.g., "I got sick", –$90) forward deterministically, for cases where Monte Carlo's full distribution isn't what's needed.

## Frequency Normalization

**File:** `model.py`

Every income and expense amount is converted to a weekly equivalent before any calculation touches it:

```python
FREQ_TO_WEEKLY = {
    "Daily":    7.0,
    "Weekly":   1.0,
    "Biweekly": 0.5,
    "Monthly":  12 / 52,   # ≈ 0.2308
}
```

`Job.weekly_income()` and `Expense.weekly_amount()` are the only two places this table is used. A monthly $1,200 rent payment and a daily $5 coffee expense both resolve to the same unit before they're compared or summed anywhere else in the system.

## Name Canonicalization

**File:** `utils.py`

Job and expense names entered inconsistently across sessions (`"Admissions"`, `"admissions"`, `"admissions office"`) need to resolve to one record rather than fragmenting into several. `normalize_job_name(raw, existing_names)` resolves in order:

1. **Exact match** (case-insensitive) against existing names
2. **Canonical-key match** via `canon_name()` — strip, drop a trailing "s" if the stem is longer than 4 characters, then title-case (`"admissions"` → `"Admission"`)
3. **Fuzzy match** using `difflib.SequenceMatcher`, accepted at a similarity ratio ≥ 0.82
4. **No match** — the input becomes a new canonical name via `canon_name()`

The function always returns the *stored* spelling when a match is found, so displays stay consistent even as new variants are typed in. `canon_name()` is a single shared function — three different call sites (`normalize_job_name()`, startup `dedup_jobs()`, and the analytics `_canon()` wrapper) all import it from `utils.py` rather than each defining their own version, which was a real bug source before it was centralized.
