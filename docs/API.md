# API Reference

`api.py` — FastAPI service, zero-logic transport over the same engine the desktop app uses. Every endpoint below is per-user-scoped where authenticated: no user can read or write another user's data.

Full interactive schemas (request/response models, try-it-out): run the server and visit **`/docs`** (Swagger UI, auto-generated from Pydantic models).

## Authentication

All endpoints except `Public` below require a `Authorization: Bearer <token>` header. Tokens are issued by `POST /api/auth/login` and verified by the `get_current_user` dependency on every protected route; missing or malformed tokens return `401`.

| Endpoint | Method | Auth | Rate limit | Description |
|---|---|---|---|---|
| `/api/health` | GET | Public | 60/min | Liveness check |
| `/api/privacy` | GET | Public | 60/min | Privacy policy as JSON |
| `/privacy` | GET | Public | 60/min | Privacy policy as an HTML page |
| `/api/auth/register` | POST | Public | 5/min | Create a new user account |
| `/api/auth/login` | POST | Public | 10/min | Authenticate, returns a signed JWT |

## State

| Endpoint | Method | Rate limit | Description |
|---|---|---|---|
| `/api/auth/me` | GET | 60/min | Current authenticated user's profile |
| `/api/state` | GET | 60/min | Full financial state summary |
| `/api/balance` | PUT | 30/min | Update the saved current balance |
| `/api/history` | GET | 60/min | Daily financial snapshots, ascending by date |
| `/api/insights` | GET | 60/min | Plain-English insights from `InsightEngine` |
| `/api/projection` | GET | 60/min | Week-by-week balance projection (`?weeks=`, default 12, max 520) |

## Jobs & Expenses

| Endpoint | Method | Rate limit | Description |
|---|---|---|---|
| `/api/jobs` | GET | 60/min | List jobs |
| `/api/jobs` | POST | 30/min | Add a job |
| `/api/jobs/{name}` | PUT | 30/min | Update a job's amount/frequency |
| `/api/jobs/{name}` | DELETE | 30/min | Delete a job |
| `/api/expenses` | GET | 60/min | List expenses |
| `/api/expenses` | POST | 30/min | Add an expense |
| `/api/expenses/{name}` | PUT | 30/min | Update an expense |
| `/api/expenses/{name}` | DELETE | 30/min | Delete an expense |

## Shifts

| Endpoint | Method | Rate limit | Description |
|---|---|---|---|
| `/api/shifts` | GET | 60/min | List shifts (optional `?day=`) |
| `/api/shifts` | POST | 30/min | Create a shift |
| `/api/shifts/{id}` | PUT | 30/min | Update a shift |
| `/api/shifts/{id}` | DELETE | 30/min | Delete a shift (`204` on success) |

## Analytics, Simulation & Optimization

| Endpoint | Method | Rate limit | Description |
|---|---|---|---|
| `/api/analytics/income` | GET | 60/min | Income grouped by job |
| `/api/analytics/efficiency` | GET | 60/min | Jobs ranked by effective $/hr |
| `/api/simulate/monte-carlo` | POST | 10/min | Run the Monte Carlo engine (`weeks`, `n`) |
| `/api/simulate/whatif` | POST | 20/min | Project a single user-described event forward |
| `/api/optimize/shifts` | POST | 20/min | 0/1 knapsack shift selection under an hour budget |

## Security Notes

- Passwords are hashed with `bcrypt`, used directly (no `passlib`).
- JWTs are signed with `SECRET_KEY` (required in the environment — see [`.env.example`](../.env.example)); there is no default key.
- `CORS_ORIGINS` must be set explicitly in production; a wildcard (`*`) is rejected at startup.
- Every protected endpoint's response body is verified (in `test_api.py`) to never leak `hashed_password`, `DATABASE_URL`, or `SECRET_KEY`.
- All string inputs (job names, expense names/categories, what-if descriptions) are stripped of HTML/script tags before being echoed back anywhere.
