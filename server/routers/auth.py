"""Staff login and logout."""
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from db import get_db
from security import verify_password
from sessions import COOKIE_NAME, SESSION_HOURS, create_session, current_staff, end_session

router = APIRouter(prefix="/api/auth", tags=["Staff login"])

MAX_FAILS = 5
LOCK_SECONDS = 15 * 60
_fails: dict[str, list[float]] = defaultdict(list)   # username -> times of recent failed attempts


class LoginIn(BaseModel):
    username: str
    password: str


def _recent_fails(username: str) -> list[float]:
    cutoff = time.time() - LOCK_SECONDS
    _fails[username] = [t for t in _fails[username] if t > cutoff]
    return _fails[username]


@router.post("/login")
def login(body: LoginIn, response: Response):
    username = body.username.strip().lower()
    if len(_recent_fails(username)) >= MAX_FAILS:
        raise HTTPException(429, "Too many wrong attempts. Try again in 15 minutes.")

    with get_db() as conn:
        row = conn.execute(
            "SELECT id, name, role, password_hash FROM staff WHERE lower(username) = ? AND active = 1", (username,)
        ).fetchone()
        if not row or not verify_password(body.password, row["password_hash"]):
            _fails[username].append(time.time())
            raise HTTPException(401, "Wrong username or password")
        _fails.pop(username, None)
        session_id = create_session(conn, row["id"])

    response.set_cookie(
        COOKIE_NAME, session_id,
        max_age=SESSION_HOURS * 3600, httponly=True, samesite="lax",
        secure=False,  # set True once the server runs on HTTPS
    )
    return {"name": row["name"], "role": row["role"]}


@router.post("/logout")
def logout(request: Request, response: Response):
    sid = request.cookies.get(COOKIE_NAME)
    if sid:
        end_session(sid)
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    staff = current_staff(request)
    if not staff:
        raise HTTPException(401, "Not logged in")
    return staff
