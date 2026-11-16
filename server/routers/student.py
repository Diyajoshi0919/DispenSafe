"""Student side: confirm a bill from the QR code."""
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db import audit, get_db
from services import get_bill, set_status, valid_token
from ws import hub

router = APIRouter(prefix="/api/confirm", tags=["Student"])


class Confirm(BaseModel):
    roll_no: str


def _mask(roll: str) -> str:
    return roll[:2] + "****" + roll[-2:] if len(roll) > 4 else "****"


@router.get("/{token}")
def view_bill(token: str):
    with get_db() as conn:
        tok = valid_token(conn, token)
        if not tok:
            raise HTTPException(404, "This QR code has expired or was already used")
        bill = get_bill(conn, tok["bill_id"])
    return {"bill_no": bill["bill_no"], "roll_no": _mask(bill["roll_no"]), "items": bill["items"], "total": bill["total"]}


@router.post("/{token}")
async def confirm_bill(token: str, body: Confirm):
    with get_db() as conn:
        tok = valid_token(conn, token)
        if not tok:
            raise HTTPException(404, "This QR code has expired or was already used")
        bill = get_bill(conn, tok["bill_id"])
        if body.roll_no.strip() != bill["roll_no"]:
            audit(conn, bill["id"], "confirm_failed", "student", "roll number mismatch")
            conn.commit()  # keep the failed attempt in the log even though we raise
            raise HTTPException(403, "Roll number does not match this bill")
        conn.execute("UPDATE confirm_tokens SET used_at = ? WHERE token = ?", (time.time(), token))
        bill = set_status(conn, bill["id"], "confirmed")
        audit(conn, bill["id"], "confirmed", f"student {bill['roll_no']}")
    await hub.broadcast("bill_confirmed", bill)
    return {"ok": True}
