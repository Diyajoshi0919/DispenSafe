"""
Database: SQLite file, schema, and sample data.

The database file is created automatically the first time the server starts.
Delete dispensafe.db to start fresh (all data is lost).
"""
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from security import hash_password

DB_PATH = os.environ.get("DB_PATH", str(Path(__file__).resolve().parent / "dispensafe.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    roll_no     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    programme   TEXT,
    hostel      TEXT,
    email       TEXT UNIQUE,
    phone       TEXT,
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS staff (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    role           TEXT NOT NULL CHECK (role IN ('opd', 'pharmacy', 'admin')),
    username       TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,
    active         INTEGER NOT NULL DEFAULT 1,
    created_at     REAL NOT NULL
);

-- roll_no is not a foreign key on purpose: a bill must be saved even if the
-- student is not yet in the students table.
CREATE TABLE IF NOT EXISTS bills (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_no           TEXT,
    job_id            TEXT UNIQUE,
    roll_no           TEXT NOT NULL,
    total             REAL,
    status            TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'approved', 'rejected', 'confirmed', 'handed_over')),
    reject_reason     TEXT,
    raw_text          TEXT,
    replaces_bill_id  INTEGER REFERENCES bills(id),
    created_at        REAL NOT NULL,
    updated_at        REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bills_status ON bills(status, created_at);
CREATE INDEX IF NOT EXISTS idx_bills_roll ON bills(roll_no);

CREATE TABLE IF NOT EXISTS bill_items (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id        INTEGER NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
    medicine_name  TEXT NOT NULL,
    qty            INTEGER NOT NULL,
    amount         REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_bill ON bill_items(bill_id);

CREATE TABLE IF NOT EXISTS prescriptions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    roll_no     TEXT NOT NULL,
    doctor_id   INTEGER REFERENCES staff(id),
    notes       TEXT,
    photo_file  TEXT,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rx_roll ON prescriptions(roll_no, created_at);

CREATE TABLE IF NOT EXISTS prescription_items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    prescription_id  INTEGER NOT NULL REFERENCES prescriptions(id) ON DELETE CASCADE,
    medicine_name    TEXT NOT NULL,
    dose             TEXT
);

CREATE TABLE IF NOT EXISTS confirm_tokens (
    token       TEXT PRIMARY KEY,
    bill_id     INTEGER NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
    created_at  REAL NOT NULL,
    expires_at  REAL NOT NULL,
    used_at     REAL
);
CREATE INDEX IF NOT EXISTS idx_tokens_bill ON confirm_tokens(bill_id);

-- Append-only: never update or delete rows here.
CREATE TABLE IF NOT EXISTS audit_log (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id  INTEGER,
    action   TEXT NOT NULL,
    actor    TEXT NOT NULL,
    detail   TEXT,
    at       REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_bill ON audit_log(bill_id);

CREATE TABLE IF NOT EXISTS otp_codes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    roll_no     TEXT NOT NULL,
    code_hash   TEXT NOT NULL,
    expires_at  REAL NOT NULL,
    attempts    INTEGER NOT NULL DEFAULT 0,
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    user_type   TEXT NOT NULL CHECK (user_type IN ('staff', 'student')),
    user_id     TEXT NOT NULL,
    expires_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS notices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  REAL NOT NULL,
    expires_at  REAL
);

CREATE TABLE IF NOT EXISTS daily_status (
    date            TEXT PRIMARY KEY,   -- YYYY-MM-DD
    opd_open        INTEGER NOT NULL DEFAULT 1,
    doctor_on_duty  TEXT,
    pharmacy_hours  TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key    TEXT PRIMARY KEY,
    value  TEXT
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def get_db():
    """Use as: with get_db() as conn: ...  Commits on success, rolls back on error, always closes."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def audit(conn, bill_id, action, actor, detail=""):
    conn.execute(
        "INSERT INTO audit_log (bill_id, action, actor, detail, at) VALUES (?, ?, ?, ?, ?)",
        (bill_id, action, actor, detail, time.time()),
    )


def init_db(seed: bool = True):
    with get_db() as conn:
        conn.executescript(SCHEMA)
        if seed and conn.execute("SELECT COUNT(*) FROM staff").fetchone()[0] == 0:
            _seed(conn)


def _seed(conn):
    """Sample data for development. Replace with real records before going live."""
    now = time.time()
    conn.executemany(
        "INSERT INTO students (roll_no, name, programme, hostel, email, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("21103045", "Riya Sharma", "B.Tech CSE", None, None, now),
            ("22104118", "Aman Verma", "B.Tech ECE", None, None, now),
            ("23103012", "Kavya Nair", "B.Tech IT", None, None, now),
        ],
    )
    conn.executemany(
        "INSERT INTO staff (name, role, username, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
        [
            ("OPD Doctor", "opd", "opd", hash_password("change-me"), now),
            ("Pharmacist", "pharmacy", "pharmacy", hash_password("change-me"), now),
            ("Admin", "admin", "admin", hash_password("change-me"), now),
        ],
    )
    # Prescription on record for the first sample student
    doc_id = conn.execute("SELECT id FROM staff WHERE username = 'opd'").fetchone()[0]
    rx = conn.execute(
        "INSERT INTO prescriptions (roll_no, doctor_id, notes, created_at) VALUES (?, ?, ?, ?)",
        ("21103045", doc_id, "Fever and cold", now),
    ).lastrowid
    conn.executemany(
        "INSERT INTO prescription_items (prescription_id, medicine_name, dose) VALUES (?, ?, ?)",
        [(rx, "Paracetamol 500mg", "1 tab TDS, 10 tabs"), (rx, "Cetirizine 10mg", "1 tab HS, 5 tabs")],
    )
    conn.execute(
        "INSERT INTO daily_status (date, opd_open, doctor_on_duty, pharmacy_hours) VALUES (?, 1, ?, ?)",
        (date.today().isoformat(), "[NAME]", "[HOURS]"),
    )
    conn.execute(
        "INSERT INTO notices (text, created_at) VALUES (?, ?)",
        ("Pharmacy bills are now verified digitally. No need to carry the paper bill to OPD.", now),
    )
    conn.execute("INSERT INTO settings (key, value) VALUES ('emergency_phone', '[PHONE]')")
