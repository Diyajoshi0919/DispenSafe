"""
Pretends to be the billing software printing to "Verify Printer".

Usage:
  python send_test_bill.py                 # sample bill for roll 21103045
  python send_test_bill.py 22104118        # another roll number
  python send_test_bill.py 22104118 extra  # adds a medicine that is not prescribed
  python send_test_bill.py none            # bill without a roll number (should NOT reach OPD)
"""
import os
import random
import socket
import sys

PORT = int(os.environ.get("LISTEN_PORT", "9100"))
roll = sys.argv[1] if len(sys.argv) > 1 else "21103045"
extra = len(sys.argv) > 2 and sys.argv[2] == "extra"
bill_no = random.randint(4000, 9999)

lines = [
    "\x1b@\x1b!\x10   CAMPUS DISPENSARY PHARMACY\x1b!\x00",
    f"Bill No: {bill_no}        Date: 14-11-2026",
    "" if roll == "none" else f"Roll No: {roll}",
    "Name: Test Student",
    "----------------------------------------",
    "Item                     Qty    Amount",
    "Paracetamol 500mg        10     20.00",
    "Cetirizine 10mg          5      15.50",
]
total = 35.50
if extra:
    lines.append("ORS Sachet               3      45.00")
    total += 45.00
lines += [
    "----------------------------------------",
    f"Total:                          {total:.2f}",
    "", "", "\x1dV\x00",
]

with socket.create_connection(("127.0.0.1", PORT), timeout=5) as s:
    s.sendall("\n".join(lines).encode("cp437"))
print(f"Test bill #{bill_no} printed for roll {roll}" + (" (with ORS, not prescribed)" if extra else ""))
