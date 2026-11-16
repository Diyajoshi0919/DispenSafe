"""Bills arriving from the print agent."""
import json
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from db import audit, get_db
from security import require_agent
from services import get_bill
from ws import hub

router = APIRouter(prefix="/api/bills", tags=["print agent"])


class Item(BaseModel):
    name: str
    qty: int = Field(gt=0)
    amount: float = Field(ge=0)


class BillIn(BaseModel):
    job_id: str
    roll_no: str
    bill_no: str | None = None
    items: list[Item]
    total: float | None = None
    raw_text: str = ""


@router.post("", dependencies=[Depends(require_agent)])
async def receive_bill(bill: BillIn):
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM bills WHERE job_id = ?", (bill.job_id,)).fetchone()
        if existing:  # the agent retried after a timeout: return the bill we already have
            return get_bill(conn, existing["id"])
        now = time.time()
        total = bill.total if bill.total is not None else round(sum(i.amount for i in bill.items), 2)
        # A new bill for a student whose last bill was rejected is treated as the corrected version.
        prev = conn.execute(
            "SELECT id FROM bills WHERE roll_no = ? AND status = 'rejected' AND created_at > ? "
            "ORDER BY created_at DESC LIMIT 1", (bill.roll_no, now - 6 * 3600)).fetchone()
        bill_id = conn.execute(
            "INSERT INTO bills (bill_no, job_id, roll_no, total, raw_text, replaces_bill_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (bill.bill_no, bill.job_id, bill.roll_no, total, bill.raw_text, prev["id"] if prev else None, now, now),
        ).lastrowid
        conn.executemany(
            "INSERT INTO bill_items (bill_id, medicine_name, qty, amount) VALUES (?, ?, ?, ?)",
            [(bill_id, i.name, i.qty, i.amount) for i in bill.items],
        )
        audit(conn, bill_id, "printed", "print-agent", bill.job_id)
        result = get_bill(conn, bill_id)
    await hub.broadcast("bill_created", result)
    return result
