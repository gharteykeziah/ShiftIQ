"""
api.py — FastAPI service exposing the ShiftIQ engine over HTTP.

This is the composition root only: it creates the app, wires up CORS and
security middleware, runs the startup DB migration, mounts the static
frontend, and includes every router. It contains zero business logic and
zero route handlers of its own (aside from the conditional static-file root
route, which is app-wiring, not a domain endpoint).

Request handling lives in routers/ (validate input, call a service, return
the result). Business logic lives in services/. Shared Pydantic models live
in schemas.py. Cross-cutting dependencies (the rate limiter, the Bearer-token
auth check, the per-request FinancialState factory) live in dependencies.py.

`app` and `limiter` are re-exported at module level because test_api.py does
`from backend.api.api import app, limiter`, and Dockerfile/render.yaml run
`uvicorn backend.api.api:app` — this file is the one guaranteed entry point.

Run locally:
    pip install -r requirements.txt
    pip install fastapi "uvicorn[standard]" pydantic
    uvicorn backend.api.api:app --reload

Then open http://127.0.0.1:8000 for the thin built-in frontend, or
http://127.0.0.1:8000/docs for interactive Swagger API docs (generated
automatically by FastAPI from the type hints in schemas.py).
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
load_dotenv()  # loads .env when running locally; no-op in production

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

import backend.core.database as db
import backend.core.db_pg as db_pg
from backend.core.db_connection import get_connection, is_postgres
from backend.core.config import CORS_ORIGINS
from backend.core.dependencies import limiter
from backend.api.routers import auth, expenses, insights, jobs, optimizer, shifts, simulation, system

app = FastAPI(
    title="ShiftIQ API",
    description="Schedule-driven financial simulation engine, exposed over HTTP.",
    version="2.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Allow only known frontend origins to call the API — configured via the
# CORS_ORIGINS env var (comma-separated). Defaults to the standard Next.js
# dev server origins (http://localhost:3000, http://127.0.0.1:3000) when
# unset. Production deployments MUST set CORS_ORIGINS to the real frontend
# domain(s), e.g. CORS_ORIGINS=https://app.shiftiq.com
#
# A wildcard ("*") is refused outright — it would let any website read
# authenticated responses via a stolen/copied Bearer token in a user's
# browser (e.g. via a malicious script making a fetch() from another tab).
# Scoping to explicit origins costs nothing since the frontend origin is
# known ahead of time, and it's the only one that should ever call this API.
#
# allow_credentials=False: this API uses Bearer tokens in the Authorization
# header, not cookies. allow_credentials=True is only required for
# cookie-based auth.
if "*" in CORS_ORIGINS:
    raise RuntimeError(
        "CORS_ORIGINS cannot include '*'. Set it to a comma-separated list "
        "of exact frontend origins, e.g. "
        "CORS_ORIGINS=https://app.shiftiq.com,http://localhost:3000"
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Security headers ──────────────────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security headers to every HTTP response.

    These headers instruct browsers to block common attack vectors:
    - nosniff:     prevent MIME-type sniffing (browser executing JSON as script)
    - DENY:        block clickjacking via <iframe> embedding
    - XSS-filter:  activate the browser's built-in XSS detector (legacy browsers)
    - Referrer:    don't leak URL details to third-party sites
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


app.add_middleware(SecurityHeadersMiddleware)


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
def _startup() -> None:
    """
    Initialise the database on startup.

    - DATABASE_URL not set  →  SQLite via database.init_db()
    - DATABASE_URL set      →  PostgreSQL via db_pg.init_db()

    No other code needs to know which backend is active — get_connection()
    handles that transparently for every query.
    """
    if is_postgres():
        with get_connection() as conn:
            db_pg.init_db(conn)
    else:
        db.init_db()
        db.init_events_table()


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(system.router)
app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(expenses.router)
app.include_router(shifts.router)
app.include_router(optimizer.router)
app.include_router(simulation.router)
app.include_router(insights.router)


# ── Thin frontend (static files) ──────────────────────────────────────────────

_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    @app.get("/")
    def root() -> FileResponse:
        return FileResponse(os.path.join(_STATIC_DIR, "index.html"))
