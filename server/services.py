"""Shared logic used by several routers."""
import secrets
import time

from fastapi import HTTPException

TOKEN_MINUTES = 15
ALLOWED = {
    "approved": {"pending"},
    "rejected": {"pending"},
    "confirmed": {"approved"},
    "handed_over": {"confirmed"},
}


def get_bill(conn, bill_id: int) -> dict:
    row = conn.execute("SELECT * FROM bills WHERE id = ?", (bill_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Bill not found")
    bill = dict(row)
    bill["items"] = [dict(r) for r in conn.execute(
        "SELECT medicine_name, qty, amount FROM bill_items WHERE bill_id = ? ORDER BY id", (bill_id,))]
    student = conn.execute("SELECT name, programme FROM students WHERE roll_no = ?", (bill["roll_no"],)).fetchone()
    bill["student"] = dict(student) if student else None
    return bill


def set_status(conn, bill_id: int, new_status: str, **fields) -> dict:
    """Change a bill's status, refusing any jump the flow does not allow."""
    bill = get_bill(conn, bill_id)
    if bill["status"] not in ALLOWED[new_status]:
        raise HTTPException(409, f"Bill is {bill['status']}; it cannot become {new_status}")
    cols = ", ".join(f"{k} = ?" for k in fields)
    sql = "UPDATE bills SET status = ?, updated_at = ?" + (f", {cols}" if cols else "") + " WHERE id = ?"
    conn.execute(sql, (new_status, time.time(), *fields.values(), bill_id))
    return get_bill(conn, bill_id)


def new_confirm_token(conn, bill_id: int) -> str:
    """Create a fresh one-time QR token; any older unused token for this bill stops working."""
    now = time.time()
    conn.execute("DELETE FROM confirm_tokens WHERE bill_id = ? AND used_at IS NULL", (bill_id,))
    token = secrets.token_urlsafe(16)
    conn.execute(
        "INSERT INTO confirm_tokens (token, bill_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, bill_id, now, now + TOKEN_MINUTES * 60),
    )
    return token


def valid_token(conn, token: str):
    return conn.execute(
        "SELECT * FROM confirm_tokens WHERE token = ? AND used_at IS NULL AND expires_at > ?",
        (token, time.time()),
    ).fetchone()


def latest_prescription(conn, roll_no: str):
    rx = conn.execute(
        "SELECT p.*, s.name AS doctor_name FROM prescriptions p LEFT JOIN staff s ON s.id = p.doctor_id "
        "WHERE p.roll_no = ? ORDER BY p.created_at DESC LIMIT 1", (roll_no,)).fetchone()
    if not rx:
        return None
    rx = dict(rx)
    rx["items"] = [dict(r) for r in conn.execute(
        "SELECT medicine_name, dose FROM prescription_items WHERE prescription_id = ? ORDER BY id", (rx["id"],))]
    return rx


def _norm(name: str) -> str:
    return "".join(name.lower().split())


def check_against_rx(bill: dict, rx) -> list[str]:
    """Names of billed medicines that are not on the prescription."""
    if not rx:
        return []
    prescribed = {_norm(i["medicine_name"]) for i in rx["items"]}
    return [i["medicine_name"] for i in bill["items"] if _norm(i["medicine_name"]) not in prescribed]
