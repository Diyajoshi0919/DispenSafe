# Setting up the Verify Printer (pharmacy PC)

The pharmacy keeps using its billing software (vSaral) exactly as today. We add one extra
printer, "Verify Printer", that sends the bill to the DispenSafe print agent instead of paper.

## 1. Add the printer (Windows 10/11)

1. **Settings → Bluetooth & devices → Printers & scanners → Add device**.
2. Wait a few seconds, then click **Add manually** ("The printer that I want isn't listed").
3. Choose **Add a printer using an IP address or hostname** → Next.
4. Device type: **TCP/IP Device**. Hostname or IP address: `127.0.0.1`. Port name: `VerifyPrinter`.
   **Untick** "Query the printer and automatically select the driver" → Next.
5. If asked for more port information: **Custom → Settings…** → Protocol **Raw**, Port number **9100** → OK → Next.
6. Driver: manufacturer **Generic**, printer **Generic / Text Only** → Next.
7. Name it **Verify Printer**. Do not set it as the default. Do not share it. Finish.
   Skip the test page.

The Text Only driver makes Windows send the bill as plain text, which the agent can read.

## 2. Run the print agent

```
cd C:\Projects\DispenSafe\print_agent
copy .env.example .env
notepad .env          # set SERVER_URL to the server PC, e.g. http://192.168.1.10:8000
python agent.py
```

You should see `Verify Printer listening on 127.0.0.1:9100`.

To start it automatically: **Task Scheduler → Create Basic Task → "When I log on"** →
Start a program → `C:\Projects\DispenSafe\print_agent\start_agent.bat`.

## 3. Test without vSaral

```
python send_test_bill.py
```

The agent window shows `roll 21103045, 2 items` and then `sent to server`.

## 4. Test with a real bill

1. In vSaral, print a bill and choose **Verify Printer**.
2. Look at the agent window:
   - `sent to server` → done, it appears on the OPD dashboard.
   - `NOT sent (no roll number found)` → the parser does not understand vSaral's layout yet.
3. To fix the layout, run the checker on the saved job:
   ```
   python parser.py spool\raw\<newest file>.prn
   ```
   It prints the text vSaral sent and what was found. Adjust the patterns at the top of
   `parser.py` (ROLL_RE, ITEM_RE, TOTAL_RE) until the result is right, then run
   `python -m pytest tests` to make sure the sample bill still works.

**The roll number must be printed on the bill.** If vSaral has no roll number field, enter it
in a field that does print (for example patient ID or remarks) and match that label in `ROLL_RE`.

## 5. Optional: keep a paper copy

Set `FORWARD_TO=<real printer IP>:9100` in `.env`. Every job is then also sent to the real
printer. This needs a network printer that accepts raw port 9100.

## Where things are saved

| Folder | Contains |
|---|---|
| `spool/raw/` | Every job exactly as printed (kept for checking and audit) |
| `spool/outbox/` | Bills waiting to be sent (server offline) |
| `spool/unparsed/` | Jobs that were not sent because something was missing |

These folders are ignored by Git, because they contain real student data.

## Common problems

| Message | Fix |
|---|---|
| `Port 9100 is already in use` | Another program (often an old agent window) is using it. Close it, or set `LISTEN_PORT=9101` in `.env` and change the printer port to 9101. |
| `server not reachable` | Server not running, wrong `SERVER_URL`, or firewall on the server PC. Bills wait and are sent automatically later. |
| `server refused the bill (401)` | `AGENT_KEY` in `print_agent/.env` differs from the one in `server/.env`. |
| Nothing appears in the agent window | The bill was printed to a different printer, or the printer port is not `127.0.0.1:9100` Raw. |
