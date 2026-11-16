"""
DispenSafe server.

Run from the server folder:
    pip install -r requirements.txt
    python -m uvicorn app:app --host 0.0.0.0 --port 8000
Home page: http://localhost:8000      API docs: http://localhost:8000/docs
"""
from pathlib import Path

try:  # read settings from server/.env if present
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from db import init_db
from routers import auth, bills, home, opd, pages, pharmacy, student
import ws

DASHBOARDS = Path(__file__).resolve().parent.parent / "dashboards"

init_db()

app = FastAPI(title="DispenSafe", description="Digital bill verification for the NIT Jalandhar campus dispensary")
app.mount("/static", StaticFiles(directory=DASHBOARDS), name="static")

for module in (auth, bills, opd, pharmacy, student, home, ws, pages):
    app.include_router(module.router)

