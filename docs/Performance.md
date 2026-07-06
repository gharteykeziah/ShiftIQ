# Performance

Benchmark for the NumPy vectorization of `run_monte_carlo()`. Implementation details are in [`Algorithms.md`](Algorithms.md).

## Monte Carlo Vectorization

The original implementation nested Python loops across simulation runs, weeks, and the 10 background random events — `n × weeks × 10` individual dice rolls per call. The current version draws all random values for a run in a single batched NumPy call and applies boolean masks across the full array at once (see `_roll_random_events_vectorized` in `simulation.py`).

| Scenario | Pure Python | Vectorized | Speedup |
|---|---|---|---|
| 500 runs / 52 weeks | 27.7 ms | 5.5 ms | 5.0× |
| 500 runs / 12 weeks | 6.5 ms | 1.7 ms | 3.8× |
| 5,000 runs / 52 weeks | 282.2 ms | 44.8 ms | 6.3× |

Both implementations use the same statistical model — every event still rolls independently per week with the same probability and dollar range. Only the computation strategy changed.

## Methodology

`scripts/benchmark_monte_carlo.py` times the current vectorized `run_monte_carlo()` against a preserved pure-Python nested-loop reference implementation, on the same machine, in the same run. Each scenario is timed as the best of 5 repetitions (`time.perf_counter()`), which reduces noise from OS scheduling and warm-up effects without hiding real variance.

Reproduce it yourself:

```bash
python3 scripts/benchmark_monte_carlo.py
```

Numbers above will vary by machine — the speedup ratio (3.8×–6.3×) is the more portable signal than the absolute millisecond values.

## Why 500 Runs

500 is the convergence point for the probability distribution used in the deficit-risk calculation. At 100 runs, `deficit_probability` has high variance between runs of the same simulation. At 500, the standard error on a 15% probability is approximately ±1.7 percentage points — sufficient precision for the decision-support use case. At 1,000, runtime doubles for marginal accuracy gain. The constant lives in `config.MONTE_CARLO_RUNS`.
