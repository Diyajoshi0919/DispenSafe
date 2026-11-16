"""HTML pages. Staff pages redirect to the login page when nobody (or the wrong role) is logged in."""
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, RedirectResponse

from sessions import allowed, current_staff

router = APIRouter(include_in_schema=False)
NO_STORE = {"Cache-Control": "no-store"}  # staff pages must never be shown from the browser cache
DASHBOARDS = Path(__file__).resolve().parent.parent.parent / "dashboards"


def _staff_page(request: Request, folder: str, roles: tuple[str, ...]):
    if not allowed(current_staff(request), roles):
        return RedirectResponse(f"/login?next=/{folder}", status_code=303, headers=NO_STORE)
    return FileResponse(DASHBOARDS / folder / "index.html", headers=NO_STORE)


@router.get("/")
def home():
    return FileResponse(DASHBOARDS / "home" / "index.html")


@router.get("/login")
def login_page():
    return FileResponse(DASHBOARDS / "login" / "index.html")


@router.get("/opd")
def opd_page(request: Request):
    return _staff_page(request, "opd", ("opd",))


@router.get("/pharmacy")
def pharmacy_page(request: Request):
    return _staff_page(request, "pharmacy", ("pharmacy",))
