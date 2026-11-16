"""
Manage staff accounts from the command line (run inside the server folder).

  python manage.py list
  python manage.py add --name "Dr. A. Kumar" --role opd --username akumar
  python manage.py password akumar          # set a new password
  python manage.py disable akumar           # blocks login, keeps history
  python manage.py enable akumar

Passwords are typed at a hidden prompt and stored only as hashes.
"""
import argparse
import getpass
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from db import get_db, init_db
from security import hash_password

MIN_LENGTH = 8


def ask_password() -> str:
    while True:
        pw = getpass.getpass("New password (min 8 characters): ")
        if len(pw) < MIN_LENGTH:
            print("Too short, try again.")
            continue
        if pw != getpass.getpass("Type it again: "):
            print("The two passwords did not match, try again.")
            continue
        return pw


def cmd_list(_):
    with get_db() as conn:
        rows = conn.execute("SELECT username, name, role, active FROM staff ORDER BY role, username").fetchall()
    print(f"{'USERNAME':<16}{'ROLE':<10}{'STATUS':<10}NAME")
    for r in rows:
        print(f"{r['username']:<16}{r['role']:<10}{'active' if r['active'] else 'disabled':<10}{r['name']}")


def cmd_add(a):
    username = a.username.strip().lower()
    with get_db() as conn:
        if conn.execute("SELECT 1 FROM staff WHERE lower(username) = ?", (username,)).fetchone():
            sys.exit(f"Username '{username}' already exists.")
    pw = ask_password()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO staff (name, role, username, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (a.name.strip(), a.role, username, hash_password(pw), time.time()),
        )
    print(f"Added {a.role} account '{username}' for {a.name}.")


def cmd_password(a):
    username = a.username.strip().lower()
    with get_db() as conn:
        if not conn.execute("SELECT 1 FROM staff WHERE lower(username) = ?", (username,)).fetchone():
            sys.exit(f"No account '{username}'.")
    pw = ask_password()
    with get_db() as conn:
        conn.execute("UPDATE staff SET password_hash = ? WHERE lower(username) = ?", (hash_password(pw), username))
        conn.execute("DELETE FROM sessions WHERE user_type = 'staff' AND user_id = "
                     "(SELECT CAST(id AS TEXT) FROM staff WHERE lower(username) = ?)", (username,))
    print(f"Password changed for '{username}'. Existing logins for this account were signed out.")


def cmd_active(a, active: int):
    username = a.username.strip().lower()
    with get_db() as conn:
        cur = conn.execute("UPDATE staff SET active = ? WHERE lower(username) = ?", (active, username))
        if cur.rowcount == 0:
            sys.exit(f"No account '{username}'.")
        if not active:
            conn.execute("DELETE FROM sessions WHERE user_type = 'staff' AND user_id = "
                         "(SELECT CAST(id AS TEXT) FROM staff WHERE lower(username) = ?)", (username,))
    print(f"'{username}' {'enabled' if active else 'disabled'}.")


def main():
    init_db()
    p = argparse.ArgumentParser(description="Manage DispenSafe staff accounts")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="show all staff accounts")
    add = sub.add_parser("add", help="create a staff account")
    add.add_argument("--name", required=True)
    add.add_argument("--role", required=True, choices=["opd", "pharmacy", "admin"])
    add.add_argument("--username", required=True)
    for name in ("password", "disable", "enable"):
        sub.add_parser(name).add_argument("username")
    a = p.parse_args()
    {"list": cmd_list, "add": cmd_add, "password": cmd_password,
     "disable": lambda x: cmd_active(x, 0), "enable": lambda x: cmd_active(x, 1)}[a.cmd](a)


if __name__ == "__main__":
    main()
