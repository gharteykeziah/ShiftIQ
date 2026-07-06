# Contributing to ShiftIQ

Thanks for your interest. This document tells you exactly how to get the project running locally, run the tests, and submit a change.

---

## Prerequisites

- Python 3.10 or higher
- `pip` (comes with Python)
- macOS, Linux, or Windows with WSL

Check your version:

```bash
python3 --version
```

---

## Setting Up Locally

```bash
git clone https://github.com/gharteykeziah-hub/shiftiq.git
cd shiftiq
pip install -r requirements.txt
```

That's it. No virtual environment is required (though one is recommended).

**macOS only:** if the app window appears blank on first launch:

```bash
brew install python-tk
```

---

## Running the App

```bash
python3 main.py
```

The app creates a `finance.db` SQLite database in the same folder on first run. This file holds your data and is excluded from version control via `.gitignore`.

To run the optional API service:

```bash
pip install -r requirements-api.txt
uvicorn api:app --reload
```

The API will be available at `http://127.0.0.1:8000` and auto-generated docs at `http://127.0.0.1:8000/docs`.

---

## Running the Tests

```bash
python3 -m pytest test_shiftiq.py -v
```

The test suite has 166 tests across 19 classes. None of them open the GUI or touch a real database — everything runs against in-memory state. A full pass takes under two seconds.

To run a specific test class:

```bash
python3 -m pytest test_shiftiq.py::TestFinancialState -v
```

CI runs the full suite automatically on every push and pull request (Python 3.10, 3.11, 3.12).

---

## Project Layout

The key files to understand before making changes:

| File | What it owns |
|---|---|
| `financial_state.py` | All financial calculations — net flow, savings rate, risk score, projections |
| `database.py` | All SQLite reads and writes |
| `model.py` | Data models (`Job`, `Expense`) and frequency conversions |
| `config.py` | All constants — change a value here, it changes everywhere |
| `exceptions.py` | Shared exceptions — raise `ValidationError` for bad user input |
| `schedule_core.py` | Shift scheduling backend |
| `simulation.py` | Monte Carlo and what-if engines |
| `app.py` | Desktop app shell, wires pages to state |
| `page_*.py` | UI pages — no logic, only display |

The rule: `page_*.py` files contain zero business logic. If you find yourself writing a calculation inside a page file, it belongs in `financial_state.py`, `shift_analytics.py`, or another engine module instead.

---

## Code Style

- **Python 3.10+** — use `match` statements, `X | Y` union types, and `dataclass` where appropriate
- **Line length:** 120 characters max
- **Exceptions:** raise `ValidationError` (from `exceptions.py`) for user input errors, never bare `ValueError`
- **Constants:** add new magic numbers to `config.py`, never inline them
- **No linter warnings:** the codebase currently passes a clean style check — keep it that way

There is no auto-formatter enforced. Match the style of the file you're editing.

---

## Making a Change

1. **Branch off `main`:**

```bash
git checkout -b your-branch-name
```

2. **Make your changes.** If you're touching financial calculations, add or update a test in `test_shiftiq.py`.

3. **Run the tests** and confirm they all pass:

```bash
python3 -m pytest test_shiftiq.py -v
```

4. **Commit with a descriptive message** using the project convention:

```
refactor:  restructuring code, no behavior change
docs:      documentation only
test:      adding or fixing tests
style:     formatting, linting
types:     type hints
chore:     config, dependencies, build
fix:       bug fix
```

Example: `fix: clamp overnight shifts at midnight in free-time calculation`

5. **Open a pull request** against `main` with a short description of what changed and why.

---

## Reporting a Bug

Open a GitHub issue with:

- What you did
- What you expected to happen
- What actually happened
- Your Python version (`python3 --version`) and OS

If the bug involves financial calculations being wrong, include the job amounts, frequencies, and balance you entered.

---

## Questions

Open an issue with the `question` label. There are no stupid questions — this codebase has a specific architecture and it takes a few minutes to get oriented.
