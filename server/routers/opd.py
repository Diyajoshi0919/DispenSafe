"""OPD dashboard API: review bills, approve or reject, record prescriptions."""
import json
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from db import audit, get_db
from sessions import require_role
from services import check_against_rx, get_bill, latest_prescription, new_confirm_token, set_status
from ws import hub

router = APIRouter(prefix="/api/opd", tags=["OPD"])
staff_only = require_role("opd")
UPLOADS = Path(__file__).resolve().parent.parent / "uploads"
UPLOADS.mkdir(exist_ok=True)


class Decision(BaseModel):
    reason: str = ""


@router.get("/bills")
def list_bills(status: str = "pending", staff: dict = Depends(staff_only)):
    statuses = [s for s in status.split(",") if s]
    since = time.time() - 24 * 3600
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT id FROM bills WHERE status IN ({','.join('?' * len(statuses))}) AND created_at > ? "
            "ORDER BY created_at DESC", (*statuses, since)).fetchall()
        return [get_bill(conn, r["id"]) for r in rows]


@router.get("/bills/{bill_id}")
def bill_detail(bill_id: int, staff: dict = Depends(staff_only)):
    with get_db() as conn:
        bill = get_bill(conn, bill_id)
        rx = latest_prescription(conn, bill["roll_no"])
        log = [dict(r) for r in conn.execute("SELECT action, actor, detail, at FROM audit_log WHERE bill_id = ? ORDER BY id", (bill_id,))]
    return {"bill": bill, "prescription": rx, "not_on_prescription": check_against_rx(bill, rx), "activity": log}


@router.post("/bills/{bill_id}/approve")
async def approve(bill_id: int, staff: dict = Depends(staff_only)):
    with get_db() as conn:
        bill = set_status(conn, bill_id, "approved")
        new_confirm_token(conn, bill_id)
        audit(conn, bill_id, "approved", staff["name"])
    await hub.broadcast("bill_approved", bill)
    return bill


@router.post("/bills/{bill_id}/reject")
async def reject(bill_id: int, d: Decision, staff: dict = Depends(staff_only)):
    if not d.reason.strip():
        raise HTTPException(400, "Give a reason so the pharmacy knows what to fix")
    with get_db() as conn:
        bill = set_status(conn, bill_id, "rejected", reject_reason=d.reason.strip())
        audit(conn, bill_id, "rejected", staff["name"], d.reason.strip())
    await hub.broadcast("bill_rejected", bill)
    return bill


@router.post("/prescriptions")
async def add_prescription(
    roll_no: str = Form(...),
    notes: str = Form(""),
    items: str = Form("[]", description='JSON list, e.g. [{"medicine_name": "Paracetamol 500mg", "dose": "1 tab TDS"}]'),
    photo: UploadFile | None = File(None),
    staff: dict = Depends(staff_only),
):
    try:
        item_list = json.loads(items)
    except json.JSONDecodeError:
        raise HTTPException(400, "items must be a JSON list")
    file_name = None
    if photo and photo.filename:
        ext = Path(photo.filename).suffix.lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp", ".pdf"}:
            raise HTTPException(400, "Upload a JPG, PNG, WEBP or PDF")
        file_name = f"{uuid.uuid4().hex}{ext}"
        (UPLOADS / file_name).write_bytes(await photo.read())
    with get_db() as conn:
        rx_id = conn.execute(
            "INSERT INTO prescriptions (roll_no, doctor_id, notes, photo_file, created_at) VALUES (?, ?, ?, ?, ?)",
            (roll_no.strip(), staff["id"], notes, file_name, time.time())).lastrowid
        conn.executemany(
            "INSERT INTO prescription_items (prescription_id, medicine_name, dose) VALUES (?, ?, ?)",
            [(rx_id, i["medicine_name"], i.get("dose", "")) for i in item_list])
    return {"id": rx_id}
