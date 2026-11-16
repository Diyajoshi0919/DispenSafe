"""Pharmacy dashboard API: today's bills, QR code, hand-over."""
import io
import os
import time

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from db import audit, get_db
from sessions import require_role
from services import get_bill, new_confirm_token, set_status
from ws import hub

router = APIRouter(prefix="/api/pharmacy", tags=["Pharmacy"])
staff_only = require_role("pharmacy")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://127.0.0.1:8000")


@router.get("/bills")
def todays_bills(staff: dict = Depends(staff_only)):
    since = time.time() - 24 * 3600
    with get_db() as conn:
        rows = conn.execute("SELECT id FROM bills WHERE created_at > ? ORDER BY created_at DESC", (since,)).fetchall()
        return [get_bill(conn, r["id"]) for r in rows]


@router.get("/bills/{bill_id}/qr.svg")
def bill_qr(bill_id: int, staff: dict = Depends(staff_only)):
    with get_db() as conn:
        bill = get_bill(conn, bill_id)
        if bill["status"] != "approved":
            raise HTTPException(409, "QR is only available after OPD approval")
        tok = conn.execute(
            "SELECT token FROM confirm_tokens WHERE bill_id = ? AND used_at IS NULL AND expires_at > ? "
            "ORDER BY created_at DESC LIMIT 1", (bill_id, time.time())).fetchone()
        token = tok["token"] if tok else new_confirm_token(conn, bill_id)  # expired: make a new one
    img = qrcode.make(f"{PUBLIC_URL}/c/{token}", image_factory=qrcode.image.svg.SvgPathImage, box_size=12)
    buf = io.BytesIO()
    img.save(buf)
    return Response(buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "no-store"})


@router.post("/bills/{bill_id}/new-qr")
async def new_qr(bill_id: int, staff: dict = Depends(staff_only)):
    with get_db() as conn:
        if get_bill(conn, bill_id)["status"] != "approved":
            raise HTTPException(409, "Bill is not waiting for the student")
        new_confirm_token(conn, bill_id)
        audit(conn, bill_id, "new_qr", staff["name"])
    return {"ok": True}


@router.post("/bills/{bill_id}/handover")
async def handover(bill_id: int, staff: dict = Depends(staff_only)):
    with get_db() as conn:
        bill = set_status(conn, bill_id, "handed_over")
        audit(conn, bill_id, "handed_over", staff["name"])
    await hub.broadcast("bill_handed_over", bill)
    return bill
