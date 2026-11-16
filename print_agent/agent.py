"""
DispenSafe print agent. Runs on the pharmacy PC.

Windows sends each bill printed to "Verify Printer" to 127.0.0.1:9100 (raw TCP).
This program:
  1. receives the print job,
  2. saves the raw bytes to spool/raw/ so nothing is ever lost,
  3. reads roll number, bill number, items and total (parser.py),
  4. queues the bill in spool/outbox/ and sends it to the server,
     retrying until the server accepts it (safe across restarts).

Run:  python agent.py
Settings: print_agent/.env (copy .env.example). Needs only the Python standard library.
"""
import asyncio
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from parser import parse_bill, problems

HERE = Path(__file__).resolve().parent


def load_env(path: Path):
    """Minimal .env reader so the agent needs no extra packages."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


load_env(HERE / ".env")

LISTEN_HOST = os.environ.get("LISTEN_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "9100"))
SERVER_URL = os.environ.get("SERVER_URL", "http://127.0.0.1:8000").rstrip("/")
AGENT_KEY = os.environ.get("AGENT_KEY", "change-me-agent")
FORWARD_TO = os.environ.get("FORWARD_TO", "")      # e.g. 192.168.1.50:9100 to also print on paper
RETRY_SECONDS = int(os.environ.get("RETRY_SECONDS", "3"))

SPOOL = HERE / "spool"
RAW_DIR = SPOOL / "raw"          # every job exactly as printed
OUTBOX = SPOOL / "outbox"        # parsed bills waiting to be sent
UNPARSED = SPOOL / "unparsed"    # jobs that need a human to look at
for d in (RAW_DIR, OUTBOX, UNPARSED):
    d.mkdir(parents=True, exist_ok=True)


def log(*args):
    print(time.strftime("%H:%M:%S"), *args, flush=True)


async def forward_to_printer(data: bytes):
    host, port = FORWARD_TO.rsplit(":", 1)
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, int(port)), 5)
        writer.write(data)
        await writer.drain()
        writer.close()
        await writer.wait_closed()
    except Exception as e:  # the paper copy is optional; never block the digital flow
        log("could not forward to the real printer:", e)


async def handle_job(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    chunks = []
    while True:  # a RAW print job ends when Windows closes the connection
        try:
            chunk = await asyncio.wait_for(reader.read(65536), timeout=30)
        except asyncio.TimeoutError:
            break
        if not chunk:
            break
        chunks.append(chunk)
    writer.close()
    data = b"".join(chunks)
    if not data:
        return

    job_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    (RAW_DIR / f"{job_id}.prn").write_bytes(data)
    log(f"job {job_id}: {len(data)} bytes received")

    if FORWARD_TO:
        asyncio.create_task(forward_to_printer(data))

    bill = parse_bill(data)
    bill["job_id"] = job_id
    issues = problems(bill)
    if issues:
        (UNPARSED / f"{job_id}.json").write_text(json.dumps(bill, indent=2), encoding="utf-8")
        log(f"job {job_id}: NOT sent ({', '.join(issues)}). Saved to spool/unparsed/. "
            f"Check it with: python parser.py spool\\raw\\{job_id}.prn")
        return

    (OUTBOX / f"{job_id}.json").write_text(json.dumps(bill), encoding="utf-8")
    log(f"job {job_id}: roll {bill['roll_no']}, {len(bill['items'])} items, total {bill['total']:.2f}")


def post_bill(bill: dict):
    """True = accepted, False = try again later, None = server refused it (do not retry)."""
    req = urllib.request.Request(
        SERVER_URL + "/api/bills",
        data=json.dumps(bill).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Agent-Key": AGENT_KEY},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return 200 <= r.status < 300
    except urllib.error.HTTPError as e:
        if e.code in (400, 401, 403, 422):
            log(f"server refused the bill ({e.code}): {e.read()[:200].decode(errors='replace')}")
            return None
        return False
    except Exception:
        return False


async def sender_loop():
    """Send everything in the outbox. Files stay until the server confirms, so nothing is lost."""
    offline_logged = False
    while True:
        for f in sorted(OUTBOX.glob("*.json")):
            bill = json.loads(f.read_text(encoding="utf-8"))
            ok = await asyncio.to_thread(post_bill, bill)
            if ok:
                f.unlink()
                log(f"job {bill['job_id']}: sent to server")
                offline_logged = False
            elif ok is None:
                f.rename(UNPARSED / f.name)
            else:
                if not offline_logged:
                    log(f"server not reachable at {SERVER_URL}; bills stay in the outbox and will be retried")
                    offline_logged = True
                break
        await asyncio.sleep(RETRY_SECONDS)


async def main():
    try:
        server = await asyncio.start_server(handle_job, LISTEN_HOST, LISTEN_PORT)
    except OSError:
        log(f"Port {LISTEN_PORT} is already in use. Close the other program using it, "
            f"or set LISTEN_PORT in .env and point Verify Printer at that port.")
        return
    log(f"Verify Printer listening on {LISTEN_HOST}:{LISTEN_PORT}")
    log(f"Sending bills to {SERVER_URL}")
    waiting = len(list(OUTBOX.glob("*.json")))
    if waiting:
        log(f"{waiting} bill(s) from earlier are waiting in the outbox")
    async with server:
        await asyncio.gather(server.serve_forever(), sender_loop())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("stopped")
