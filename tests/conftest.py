"""Test setup: every test run uses a fresh temporary database, never the real one."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "print_agent"))
