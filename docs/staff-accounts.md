# Staff accounts

Staff log in at `/login` with a username and password. Accounts are managed from the
command line on the server PC, inside the `server` folder.

| Task | Command |
|---|---|
| See all accounts | `python manage.py list` |
| Add a doctor | `python manage.py add --name "Dr. A. Kumar" --role opd --username akumar` |
| Add a pharmacist | `python manage.py add --name "R. Singh" --role pharmacy --username rsingh` |
| Reset a password | `python manage.py password akumar` |
| Block someone who left | `python manage.py disable akumar` |
| Unblock | `python manage.py enable akumar` |

- You type the password at a hidden prompt (nothing shows while typing). Minimum 8 characters.
- Resetting a password or disabling an account signs that person out everywhere.
- Disable instead of deleting, so the audit log keeps showing who did what.
- Roles: `opd` (OPD dashboard), `pharmacy` (pharmacy dashboard), `admin` (both).

## Before going live

The sample accounts `opd`, `pharmacy` and `admin` all use the password `change-me`.
Create real accounts, then run `python manage.py disable opd` (and the same for `pharmacy`)
and change the admin password with `python manage.py password admin`.

## Security notes

- Passwords are stored only as salted PBKDF2 hashes.
- After 5 wrong passwords an account is locked for 15 minutes.
- Sessions last 12 hours, then staff log in again.
- The session cookie is HttpOnly (page scripts cannot read it). When the server moves to
  HTTPS, set `secure=True` in `server/routers/auth.py`.
