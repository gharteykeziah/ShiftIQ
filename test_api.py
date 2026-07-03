"""
test_api.py — API endpoint tests using FastAPI's TestClient.

Every endpoint added in Phase 1 and Phase 2 is covered here.
Tests run against a fresh in-memory SQLite database — never touches finance.db.

Run with:
    pytest test_api.py -v
"""
from __future__ import annotations

import os
import pytest
import tempfile

# Point to a temp DB before importing anything that touches the database
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["SQLITE_FILE"] = _tmp.name
os.environ["DATABASE_URL"] = ""   # force SQLite mode

from fastapi.testclient import TestClient
import db_connection
import database
from api import app

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_db(monkeypatch, tmp_path):
    """Each test gets its own empty database."""
    db_file = str(tmp_path / "api_test.db")
    monkeypatch.setattr(db_connection, "SQLITE_FILE", db_file)
    database.init_db()
    database.init_events_table()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def authed_client(client):
    """TestClient pre-authenticated with a valid JWT token.

    Registers a test user, logs in, then sets the Authorization header on
    the session so every subsequent request is authenticated automatically.
    Protected endpoints require this fixture; public endpoints use `client`.
    """
    client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "testpass123"
    })
    r = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "testpass123"
    })
    token = r.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


# ── Health (public) ───────────────────────────────────────────────────────────

class TestHealth:

    def test_health_returns_ok(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


# ── Privacy (public) ──────────────────────────────────────────────────────────

class TestPrivacy:

    def test_privacy_json(self, client):
        r = client.get("/api/privacy")
        assert r.status_code == 200
        assert "sections" in r.json()

    def test_privacy_html(self, client):
        r = client.get("/privacy")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]


# ── Auth endpoints (public) ───────────────────────────────────────────────────

class TestAuth:

    def test_register_creates_user(self, client):
        r = client.post("/api/auth/register", json={
            "email": "aba@example.com",
            "password": "securepass99"
        })
        assert r.status_code == 201
        data = r.json()
        assert data["email"] == "aba@example.com"
        # hashed_password must never appear in the response
        assert "password" not in data
        assert "hashed_password" not in data

    def test_register_duplicate_email_rejected(self, client):
        client.post("/api/auth/register", json={
            "email": "aba@example.com", "password": "securepass99"
        })
        r = client.post("/api/auth/register", json={
            "email": "aba@example.com", "password": "different123"
        })
        assert r.status_code == 409

    def test_register_invalid_email_rejected(self, client):
        r = client.post("/api/auth/register", json={
            "email": "notanemail", "password": "securepass99"
        })
        assert r.status_code == 422

    def test_register_short_password_rejected(self, client):
        r = client.post("/api/auth/register", json={
            "email": "aba@example.com", "password": "short"
        })
        assert r.status_code == 422

    def test_login_returns_token(self, client):
        client.post("/api/auth/register", json={
            "email": "aba@example.com", "password": "securepass99"
        })
        r = client.post("/api/auth/login", json={
            "email": "aba@example.com", "password": "securepass99"
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password_rejected(self, client):
        client.post("/api/auth/register", json={
            "email": "aba@example.com", "password": "securepass99"
        })
        r = client.post("/api/auth/login", json={
            "email": "aba@example.com", "password": "wrongpassword"
        })
        assert r.status_code == 401

    def test_login_unknown_email_rejected(self, client):
        r = client.post("/api/auth/login", json={
            "email": "nobody@example.com", "password": "anypassword"
        })
        assert r.status_code == 401

    def test_login_wrong_and_unknown_same_error(self, client):
        """Wrong password and unknown email must return the same message
        so attackers can't enumerate which emails are registered."""
        client.post("/api/auth/register", json={
            "email": "aba@example.com", "password": "securepass99"
        })
        r_wrong = client.post("/api/auth/login", json={
            "email": "aba@example.com", "password": "wrongpassword"
        })
        r_unknown = client.post("/api/auth/login", json={
            "email": "nobody@example.com", "password": "anypassword"
        })
        assert r_wrong.json()["detail"] == r_unknown.json()["detail"]

    def test_me_returns_profile(self, authed_client):
        r = authed_client.get("/api/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == "test@example.com"
        assert "id" in data
        assert "created_at" in data
        # hashed_password must never appear
        assert "hashed_password" not in data
        assert "password" not in data

    def test_me_without_token_rejected(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 401


# ── Auth required (protected endpoints return 401 without token) ──────────────

class TestAuthRequired:
    """Verify that every protected endpoint rejects unauthenticated requests."""

    def test_state_requires_auth(self, client):
        assert client.get("/api/state").status_code == 401

    def test_balance_requires_auth(self, client):
        assert client.put("/api/balance", json={"amount": 500}).status_code == 401

    def test_list_jobs_requires_auth(self, client):
        assert client.get("/api/jobs").status_code == 401

    def test_add_job_requires_auth(self, client):
        assert client.post("/api/jobs", json={
            "name": "X", "amount": 100, "frequency": "Weekly"
        }).status_code == 401

    def test_list_expenses_requires_auth(self, client):
        assert client.get("/api/expenses").status_code == 401

    def test_history_requires_auth(self, client):
        assert client.get("/api/history").status_code == 401

    def test_insights_requires_auth(self, client):
        assert client.get("/api/insights").status_code == 401

    def test_projection_requires_auth(self, client):
        assert client.get("/api/projection").status_code == 401

    def test_monte_carlo_requires_auth(self, client):
        assert client.post("/api/simulate/monte-carlo",
                           json={"weeks": 4, "n": 10}).status_code == 401

    def test_whatif_requires_auth(self, client):
        assert client.post("/api/simulate/whatif", json={
            "description": "Test", "dollar_change": -100, "weeks": 4
        }).status_code == 401


# ── State ─────────────────────────────────────────────────────────────────────

class TestState:

    def test_state_returns_all_fields(self, authed_client):
        r = authed_client.get("/api/state")
        assert r.status_code == 200
        data = r.json()
        for key in ("balance", "weekly_income", "weekly_expenses",
                    "net_weekly_flow", "savings_rate", "risk_score", "health_score"):
            assert key in data

    def test_state_default_balance_is_zero(self, authed_client):
        r = authed_client.get("/api/state")
        assert r.json()["balance"] == 0.0


# ── Balance ───────────────────────────────────────────────────────────────────

class TestBalance:

    def test_update_balance(self, authed_client):
        r = authed_client.put("/api/balance", json={"amount": 500.0})
        assert r.status_code == 200
        assert r.json()["balance"] == 500.0

    def test_updated_balance_reflected_in_state(self, authed_client):
        authed_client.put("/api/balance", json={"amount": 750.0})
        r = authed_client.get("/api/state")
        assert r.json()["balance"] == 750.0

    def test_negative_balance_rejected(self, authed_client):
        r = authed_client.put("/api/balance", json={"amount": -1.0})
        assert r.status_code == 422   # pydantic validation (ge=0)

    def test_zero_balance_accepted(self, authed_client):
        r = authed_client.put("/api/balance", json={"amount": 0.0})
        assert r.status_code == 200


# ── Jobs ──────────────────────────────────────────────────────────────────────

class TestJobs:

    def test_list_jobs_empty(self, authed_client):
        r = authed_client.get("/api/jobs")
        assert r.status_code == 200
        assert r.json() == []

    def test_add_job(self, authed_client):
        r = authed_client.post("/api/jobs", json={"name": "Barista", "amount": 300, "frequency": "Weekly"})
        assert r.status_code == 201
        assert r.json()["name"] == "Barista"

    def test_add_job_appears_in_list(self, authed_client):
        authed_client.post("/api/jobs", json={"name": "Barista", "amount": 300, "frequency": "Weekly"})
        r = authed_client.get("/api/jobs")
        assert len(r.json()) == 1

    def test_add_duplicate_job_rejected(self, authed_client):
        authed_client.post("/api/jobs", json={"name": "Barista", "amount": 300, "frequency": "Weekly"})
        r = authed_client.post("/api/jobs", json={"name": "Barista", "amount": 200, "frequency": "Weekly"})
        assert r.status_code == 400

    def test_delete_job(self, authed_client):
        authed_client.post("/api/jobs", json={"name": "Barista", "amount": 300, "frequency": "Weekly"})
        r = authed_client.delete("/api/jobs/Barista")
        assert r.status_code == 200

    def test_delete_job_removes_from_list(self, authed_client):
        authed_client.post("/api/jobs", json={"name": "Barista", "amount": 300, "frequency": "Weekly"})
        authed_client.delete("/api/jobs/Barista")
        r = authed_client.get("/api/jobs")
        assert r.json() == []

    def test_delete_nonexistent_job_returns_404(self, authed_client):
        r = authed_client.delete("/api/jobs/Ghost")
        assert r.status_code == 404

    def test_update_job(self, authed_client):
        authed_client.post("/api/jobs", json={"name": "Barista", "amount": 300, "frequency": "Weekly"})
        r = authed_client.put("/api/jobs/Barista", json={"name": "Barista", "amount": 350, "frequency": "Weekly"})
        assert r.status_code == 200
        assert r.json()["amount"] == 350

    def test_update_nonexistent_job_returns_404(self, authed_client):
        r = authed_client.put("/api/jobs/Ghost", json={"name": "Ghost", "amount": 100, "frequency": "Weekly"})
        assert r.status_code == 404

    def test_xss_in_job_name_stripped(self, authed_client):
        """HTML tags in job name must be stripped before storage."""
        r = authed_client.post("/api/jobs", json={
            "name": "<script>alert(1)</script>Barista",
            "amount": 300,
            "frequency": "Weekly"
        })
        assert r.status_code == 201
        assert "<script>" not in r.json()["name"]

    def test_two_users_jobs_isolated(self, client):
        """Jobs added by user A must not appear for user B."""
        # User A
        client.post("/api/auth/register", json={"email": "a@x.com", "password": "passpass1"})
        r = client.post("/api/auth/login", json={"email": "a@x.com", "password": "passpass1"})
        token_a = r.json()["access_token"]

        # User B
        client.post("/api/auth/register", json={"email": "b@x.com", "password": "passpass2"})
        r = client.post("/api/auth/login", json={"email": "b@x.com", "password": "passpass2"})
        token_b = r.json()["access_token"]

        # A adds a job
        client.post("/api/jobs",
                    json={"name": "Starbucks", "amount": 300, "frequency": "Weekly"},
                    headers={"Authorization": f"Bearer {token_a}"})

        # B's job list must be empty
        r = client.get("/api/jobs", headers={"Authorization": f"Bearer {token_b}"})
        assert r.json() == []


# ── Expenses ──────────────────────────────────────────────────────────────────

class TestExpenses:

    def test_list_expenses_empty(self, authed_client):
        r = authed_client.get("/api/expenses")
        assert r.status_code == 200
        assert r.json() == []

    def test_add_expense(self, authed_client):
        r = authed_client.post("/api/expenses", json={
            "name": "Rent", "amount": 700, "category": "Housing",
            "date": "2026-01-01", "frequency": "Monthly"
        })
        assert r.status_code == 201
        assert r.json()["name"] == "Rent"

    def test_add_expense_appears_in_list(self, authed_client):
        authed_client.post("/api/expenses", json={
            "name": "Rent", "amount": 700, "category": "Housing",
            "date": "2026-01-01", "frequency": "Monthly"
        })
        r = authed_client.get("/api/expenses")
        assert len(r.json()) == 1

    def test_delete_expense(self, authed_client):
        authed_client.post("/api/expenses", json={
            "name": "Rent", "amount": 700, "category": "Housing",
            "date": "2026-01-01", "frequency": "Monthly"
        })
        r = authed_client.delete("/api/expenses/Rent")
        assert r.status_code == 200

    def test_delete_nonexistent_expense_returns_404(self, authed_client):
        r = authed_client.delete("/api/expenses/Ghost")
        assert r.status_code == 404

    def test_update_expense(self, authed_client):
        authed_client.post("/api/expenses", json={
            "name": "Rent", "amount": 700, "category": "Housing",
            "date": "2026-01-01", "frequency": "Monthly"
        })
        r = authed_client.put("/api/expenses/Rent", json={
            "name": "Rent", "amount": 800, "category": "Housing",
            "date": "2026-01-01", "frequency": "Monthly"
        })
        assert r.status_code == 200
        assert r.json()["amount"] == 800


# ── Projection ────────────────────────────────────────────────────────────────

class TestProjection:

    def test_projection_default_12_weeks(self, authed_client):
        r = authed_client.get("/api/projection")
        assert r.status_code == 200
        assert len(r.json()["timeline"]) == 12

    def test_projection_custom_weeks(self, authed_client):
        r = authed_client.get("/api/projection?weeks=4")
        assert len(r.json()["timeline"]) == 4

    def test_projection_has_required_fields(self, authed_client):
        r = authed_client.get("/api/projection")
        data = r.json()
        assert "starting_balance" in data
        assert "net_weekly_flow" in data
        assert "timeline" in data

    def test_projection_weeks_out_of_range(self, authed_client):
        r = authed_client.get("/api/projection?weeks=999")
        assert r.status_code == 400


# ── Insights ──────────────────────────────────────────────────────────────────

class TestInsights:

    def test_insights_returns_scores(self, authed_client):
        r = authed_client.get("/api/insights")
        assert r.status_code == 200
        data = r.json()
        assert "health_score" in data
        assert "risk_score" in data
        assert "insights" in data

    def test_insights_list_is_list(self, authed_client):
        r = authed_client.get("/api/insights")
        assert isinstance(r.json()["insights"], list)


# ── History ───────────────────────────────────────────────────────────────────

class TestHistory:

    def test_history_returns_count_and_snapshots(self, authed_client):
        r = authed_client.get("/api/history")
        assert r.status_code == 200
        data = r.json()
        assert "count" in data
        assert "snapshots" in data

    def test_history_snapshots_is_list(self, authed_client):
        r = authed_client.get("/api/history")
        assert isinstance(r.json()["snapshots"], list)


# ── Simulation ────────────────────────────────────────────────────────────────

class TestSimulation:

    def test_monte_carlo(self, authed_client):
        r = authed_client.post("/api/simulate/monte-carlo", json={"weeks": 4, "n": 50})
        assert r.status_code == 200
        data = r.json()
        assert "average" in data
        assert "deficit_probability" in data

    def test_whatif(self, authed_client):
        r = authed_client.post("/api/simulate/whatif", json={
            "description": "Car repair", "dollar_change": -400, "weeks": 4
        })
        assert r.status_code == 200
        assert "history" in r.json()
