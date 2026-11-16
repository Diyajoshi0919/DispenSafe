"""Staff login, roles and protected pages. Run: python -m pytest tests"""
import pytest
from fastapi.testclient import TestClient

from app import app
from db import get_db
from routers import auth as auth_router

AGENT = {"X-Agent-Key": "change-me-agent"}


@pytest.fixture(autouse=True)
def reset_lockouts():
    auth_router._fails.clear()


def client():
    return TestClient(app)


def login(c, username, password="change-me"):
    return c.post("/api/auth/login", json={"username": username, "password": password})


def make_bill(c, job):
    r = c.post("/api/bills", headers=AGENT, json={
        "job_id": job, "roll_no": "22104118",
        "items": [{"name": "Pantoprazole 40mg", "qty": 10, "amount": 65}]})
    assert r.status_code == 200
    return r.json()["id"]


def test_wrong_password_is_refused():
    r = login(client(), "opd", "nope")
    assert r.status_code == 401
    assert "ds_session" not in r.cookies


def test_locked_after_five_wrong_attempts():
    c = client()
    for _ in range(5):
        assert login(c, "opd", "nope").status_code == 401
    assert login(c, "opd").status_code == 429  # even the right password waits


def test_login_sets_cookie_and_me_works():
    c = client()
    r = login(c, "OPD")  # usernames are not case-sensitive
    assert r.status_code == 200 and r.json()["role"] == "opd"
    assert c.get("/api/auth/me").json()["username"] == "opd"


def test_api_needs_login():
    assert client().get("/api/opd/bills").status_code == 401
    assert client().get("/api/pharmacy/bills").status_code == 401


def test_roles_are_enforced():
    c = client()
    login(c, "pharmacy")
    assert c.get("/api/opd/bills").status_code == 403
    assert c.get("/api/pharmacy/bills").status_code == 200


def test_admin_can_use_both():
    c = client()
    login(c, "admin")
    assert c.get("/api/opd/bills").status_code == 200
    assert c.get("/api/pharmacy/bills").status_code == 200


def test_pages_redirect_to_login():
    c = client()
    r = c.get("/opd", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login?next=/opd"
    login(c, "opd")
    page = c.get("/opd", follow_redirects=False)
    assert page.status_code == 200 and page.headers["cache-control"] == "no-store"
    assert c.get("/pharmacy", follow_redirects=False).status_code == 303  # wrong role


def test_actions_are_recorded_under_the_staff_name():
    c = client()
    bill_id = make_bill(c, "auth-job-1")
    login(c, "opd")
    assert c.post(f"/api/opd/bills/{bill_id}/approve").status_code == 200
    with get_db() as conn:
        actor = conn.execute("SELECT actor FROM audit_log WHERE bill_id = ? AND action = 'approved'", (bill_id,)).fetchone()[0]
    assert actor == "OPD Doctor"


def test_logout_ends_the_session():
    c = client()
    login(c, "opd")
    c.post("/api/auth/logout")
    assert c.get("/api/auth/me").status_code == 401


def test_disabled_account_cannot_log_in():
    with get_db() as conn:
        conn.execute("UPDATE staff SET active = 0 WHERE username = 'pharmacy'")
    try:
        assert login(client(), "pharmacy").status_code == 401
    finally:
        with get_db() as conn:
            conn.execute("UPDATE staff SET active = 1 WHERE username = 'pharmacy'")
