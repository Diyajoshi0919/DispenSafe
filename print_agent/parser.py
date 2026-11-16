"""
Turns raw printer bytes into a bill: roll number, bill number, items, total.

The patterns below match the sample bill in send_test_bill.py.
To tune them for the real billing software (vSaral):
  1. Print one real bill to "Verify Printer" with the agent running.
  2. Run:  python parser.py spool\\raw\\<newest file>.prn
  3. Adjust the patterns until roll number, items and total come out right.
"""
import re
import sys

# Roll number: "Roll No: 21103045", "Roll Number - 21103045", "Student ID: 21103045"
ROLL_RE = re.compile(r"(?:roll\s*(?:no\.?|number)?|student\s*id)\s*[:\-#]?\s*([0-9]{6,10})", re.I)

# Bill number: "Bill No: 4521", "Invoice No. 4521"
BILL_NO_RE = re.compile(r"(?:bill|invoice|receipt)\s*(?:no\.?|number|#)\s*[:\-]?\s*([A-Za-z0-9\-/]+)", re.I)

# Item line: "<name>  <qty>  <amount>"  e.g. "Paracetamol 500mg       10     20.00"
# Needs at least two spaces between the name and the quantity.
ITEM_RE = re.compile(
    r"^\s*(?:\d+[.)]\s+)?(?P<name>[A-Za-z][\w .\-/%+()]*?)\s{2,}(?P<qty>\d+)\s+(?P<amount>[\d,]+\.\d{2})\s*$"
)

# Total: "Total: 80.50", "Grand Total Rs. 80.50", "Net Amount ₹80.50"
TOTAL_RE = re.compile(
    r"(?:grand\s*total|net\s*amount|total\s*amount|total)\s*[:\-]?\s*(?:rs\.?|inr|\u20b9)?\s*([\d,]+\.\d{2})", re.I
)

# Lines that look like items but are not
SKIP_RE = re.compile(r"total|amount|subtotal|discount|tax|gst|balance|paid|change", re.I)

# Printer control codes: ESC/POS (thermal), PCL and ANSI sequences
ESCAPES = re.compile(
    rb"\x1b[!\-EGMVartU{][\x00-\xff]"      # ESC + command + one parameter byte
    rb"|\x1b\[[0-?]*[ -/]*[@-~]"           # ANSI / CSI
    rb"|\x1b[\x20-\x2f]*[\x30-\x7e]"       # other ESC sequences
    rb"|\x1d.[\x00-\xff]?"                 # GS commands (cut paper, etc.)
)
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def to_text(data: bytes) -> str:
    data = ESCAPES.sub(b"", data)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("cp437", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
    return CONTROL.sub("", text)


def parse_bill(data: bytes) -> dict:
    text = to_text(data)
    roll = ROLL_RE.search(text)
    bill_no = BILL_NO_RE.search(text)

    items = []
    for line in text.splitlines():
        if SKIP_RE.search(line):
            continue
        m = ITEM_RE.match(line)
        if m:
            items.append({
                "name": " ".join(m["name"].split()),
                "qty": int(m["qty"]),
                "amount": float(m["amount"].replace(",", "")),
            })

    totals = TOTAL_RE.findall(text)
    total = float(totals[-1].replace(",", "")) if totals else round(sum(i["amount"] for i in items), 2)

    return {
        "roll_no": roll.group(1) if roll else None,
        "bill_no": bill_no.group(1) if bill_no else None,
        "items": items,
        "total": total,
        "raw_text": text.strip(),
    }


def problems(bill: dict) -> list[str]:
    """Reasons a parsed bill should not be sent to the OPD."""
    out = []
    if not bill["roll_no"]:
        out.append("no roll number found")
    if not bill["items"]:
        out.append("no medicine lines found")
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python parser.py <file.prn>")
        sys.exit(1)
    with open(sys.argv[1], "rb") as f:
        bill = parse_bill(f.read())
    print("----- text the printer sent -----")
    print(bill["raw_text"])
    print("----- what the parser found -----")
    print("Roll number:", bill["roll_no"])
    print("Bill number:", bill["bill_no"])
    for i in bill["items"]:
        print(f"  {i['name']:<30} qty {i['qty']:>3}   {i['amount']:>8.2f}")
    print("Total:", bill["total"])
    issues = problems(bill)
    print("Problems:", ", ".join(issues) if issues else "none")
