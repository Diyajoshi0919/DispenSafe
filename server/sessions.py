"""
Staff login sessions.

After a successful login the browser gets an HttpOnly cookie holding a random session id.
Every request to a staff API or page looks that id up in the sessions table.
"""
import secrets
import time

from fastapi import HTTPException, Request

from db import get_db

COOKIE_NAME = "ds_session"
SESSION_HOURS = 12


def create_session(conn, staff_id: int) -> str:
    now = time.time()
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))  # tidy up old ones
    session_id = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (session_id, user_type, user_id, expires_at) VALUES (?, 'staff', ?, ?)",
        (session_id, str(staff_id), now + SESSION_HOURS * 3600),
    )
    return session_id


def end_session(session_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))


def staff_from_session(session_id: str | None) -> dict | None:
    if not session_id:
        return None
    with get_db() as conn:
        row = conn.execute(
            "SELECT s.id, s.name, s.role, s.username FROM sessions x "
            "JOIN staff s ON s.id = CAST(x.user_id AS INTEGER) "
            "WHERE x.session_id = ? AND x.user_type = 'staff' AND x.expires_at > ? AND s.active = 1",
            (session_id, time.time()),
        ).fetchone()
    return dict(row) if row else None


def current_staff(request: Request) -> dict | None:
    return staff_from_session(request.cookies.get(COOKIE_NAME))


def allowed(staff: dict | None, roles: tuple[str, ...]) -> bool:
    return bool(staff) and (staff["role"] in roles or staff["role"] == "admin")


def require_role(*roles: str):
    """FastAPI dependency: the logged-in staff member, or 401/403. Admin may use everything."""
    def dependency(request: Request) -> dict:
        staff = current_staff(request)
        if not staff:
            raise HTTPException(401, "Please log in")
        if not allowed(staff, roles):
            raise HTTPException(403, "Your account cannot use this dashboard")
        return staff
    return dependency
