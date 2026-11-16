# DispenSafe database

SQLite, one file: `server/dispensafe.db` (created on first start, never committed to Git).
Schema lives in `server/db.py`. Delete the file to start fresh during development.

## Tables

| Table | Purpose | Key columns |
|---|---|---|
| `students` | Student records | `roll_no` (PK), `name`, `programme`, `hostel`, `email`, `phone` |
| `staff` | OPD, pharmacy and admin logins | `id`, `name`, `role` (opd/pharmacy/admin), `username`, `password_hash`, `active` |
| `bills` | One row per printed bill | `id`, `bill_no`, `job_id` (unique), `roll_no`, `total`, `status`, `reject_reason`, `raw_text`, `replaces_bill_id` |
| `bill_items` | Medicines on a bill | `bill_id`, `medicine_name`, `qty`, `amount` |
| `prescriptions` | Doctor's prescription | `id`, `roll_no`, `doctor_id`, `notes`, `photo_file` |
| `prescription_items` | Medicines on a prescription | `prescription_id`, `medicine_name`, `dose` |
| `confirm_tokens` | One-time QR codes | `token` (PK), `bill_id`, `expires_at`, `used_at` |
| `audit_log` | Every action, append-only | `bill_id`, `action`, `actor`, `detail`, `at` |
| `otp_codes` | Student email login codes | `roll_no`, `code_hash`, `expires_at`, `attempts` |
| `sessions` | Logged-in users | `session_id`, `user_type`, `user_id`, `expires_at` |
| `notices` | Home page live updates | `text`, `active`, `expires_at` |
| `daily_status` | "Today at the dispensary" panel | `date`, `opd_open`, `doctor_on_duty`, `pharmacy_hours` |
| `settings` | Small key/value settings | `key`, `value` (e.g. `emergency_phone`) |

## Relationships

```
students ─< bills ─< bill_items
   │          ├─< confirm_tokens
   │          └─< audit_log
   └─< prescriptions ─< prescription_items
staff ─< prescriptions (doctor_id)
bills ─ replaces_bill_id ─> bills   (corrected bill points to the rejected one)
```

`bills.roll_no` is deliberately not a foreign key: a bill must be saved even if the student is not in `students` yet.

## Bill status flow

```
pending ──approve──> approved ──student confirms──> confirmed ──hand over──> handed_over
   └────reject────> rejected   (pharmacy prints a corrected bill → new pending bill)
```

## Audit actions

`printed`, `approved`, `rejected`, `new_qr`, `confirm_failed`, `confirmed`, `handed_over`.

## Sample data (development only)

Created automatically on first start: three students (21103045, 22104118, 23103012),
staff logins `opd`, `pharmacy`, `admin` with password `change-me`, one prescription, one notice.
Replace with real records before going live.

## Privacy

- Passwords and OTP codes are stored only as hashes.
- Store only the student details the dashboards show.
- Agree a retention period with the dispensary and back up the file regularly.
