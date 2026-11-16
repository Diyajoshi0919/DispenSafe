"""Data for the public home page."""
import time
from datetime import date

from fastapi import APIRouter

from db import get_db

router = APIRouter(prefix="/api", tags=["Home page"])


@router.get("/home")
def home_data():
    with get_db() as conn:
        st = conn.execute("SELECT * FROM daily_status WHERE date = ?", (date.today().isoformat(),)).fetchone()
        waiting = conn.execute("SELECT COUNT(*) FROM bills WHERE status = 'pending'").fetchone()[0]
        notices = [r["text"] for r in conn.execute(
            "SELECT text FROM notices WHERE active = 1 AND (expires_at IS NULL OR expires_at > ?) ORDER BY created_at DESC",
            (time.time(),))]
        phone = conn.execute("SELECT value FROM settings WHERE key = 'emergency_phone'").fetchone()
    return {
        "opd_open": bool(st["opd_open"]) if st else False,
        "doctor_on_duty": st["doctor_on_duty"] if st else None,
        "pharmacy_hours": st["pharmacy_hours"] if st else None,
        "bills_waiting": waiting,
        "emergency_phone": phone["value"] if phone else None,
        "notices": notices,
    }
