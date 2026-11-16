"""Run from the project folder:  python -m pytest tests   (or: python tests/test_parser.py)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "print_agent"))
from parser import parse_bill, problems  # noqa: E402

SAMPLE = (
    b"\x1b@\x1b!\x10   CAMPUS DISPENSARY PHARMACY\x1b!\x00\n"
    b"Bill No: 4521        Date: 14-11-2026\n"
    b"Roll No: 21103045\n"
    b"Item                     Qty    Amount\n"
    b"Paracetamol 500mg        10     20.00\n"
    b"Cetirizine 10mg          5      15.50\n"
    b"Total:                          35.50\n\x1dV\x00"
)


def test_reads_sample_bill():
    b = parse_bill(SAMPLE)
    assert b["roll_no"] == "21103045"
    assert b["bill_no"] == "4521"
    assert b["total"] == 35.50
    assert b["items"] == [
        {"name": "Paracetamol 500mg", "qty": 10, "amount": 20.0},
        {"name": "Cetirizine 10mg", "qty": 5, "amount": 15.5},
    ]
    assert problems(b) == []


def test_strips_printer_codes():
    assert "\x1b" not in parse_bill(SAMPLE)["raw_text"]
    assert parse_bill(SAMPLE)["raw_text"].startswith("CAMPUS DISPENSARY PHARMACY")


def test_flags_missing_roll_number():
    b = parse_bill(SAMPLE.replace(b"Roll No: 21103045\n", b""))
    assert "no roll number found" in problems(b)


def test_total_line_is_not_an_item():
    names = [i["name"] for i in parse_bill(SAMPLE)["items"]]
    assert not any("Total" in n for n in names)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok  ", name)
