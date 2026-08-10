# Juicetification Director

A control app for the five Juicetification operations-management simulations. This
build delivers the **foundation and access control**: a secure login, a top-level
**Grand Director (administrator)** who grants access, and management of multiple
instructors. Configuration builders and game/join-code creation are the next phases;
the database schema for them is already in place, so they add on without rework.

## What works now

- **First-run setup** — the first time you open the app, it asks you to create the
  Grand Director account. No secrets file to edit.
- **Login / logout** with PBKDF2 password hashing (standard library — no extra
  packages to install).
- **Administrator console** — add instructors, disable/enable them, reset their
  password (forces a change at next login), promote to admin or demote, and remove
  accounts. The **last active administrator is protected** and can't be removed,
  demoted, or disabled.
- **Forced password change** when an account is created or reset with a temporary
  password.
- **Activity log** of every access-control action.
- **Instructor dashboard** placeholder listing the five apps, ready for the
  configuration and game phases.

## Files

| File | Purpose |
|---|---|
| `director_app.py` | Streamlit UI, login, routing, admin console |
| `director_db.py` | SQLite schema (all phases) + instructor/audit CRUD |
| `director_auth.py` | PBKDF2 password hashing & verification |
| `requirements.txt` | Just `streamlit` |
| `director.sqlite` | Created automatically on first run |

## Run locally

```bash
cd "Juicetification Director"
pip install -r requirements.txt
streamlit run director_app.py
```

Open the URL Streamlit prints, then create your Grand Director account.

## Deploy on Streamlit Community Cloud

Push this folder to a repo and point a new Streamlit app at `director_app.py`.

**One caveat about data persistence:** Community Cloud's filesystem is ephemeral —
`director.sqlite` resets when the app is rebuilt or sleeps for a long stretch. That's
fine for trying it out. For a durable roster of instructors you'll want a hosted
database (Postgres/Supabase); the data layer is isolated in `director_db.py`, so
that swap is contained to one file. This matches the "shared store" decision noted
in the plan.

## Security notes

- Passwords are never stored in clear — only PBKDF2-HMAC-SHA256 hashes with a
  per-user salt and 200,000 iterations.
- Email uniqueness is case-insensitive.
- All database access uses parameterized queries.
- Set a strong Grand Director password; that account controls the whole system.

## Roadmap (from the plan)

1. ✅ Foundation + access control (this build)
2. Configurations — schema-driven forms per app, saved as named presets
3. Games — bind a config to a class, mint a join code, launch links + QR
4. Wire the join code into each sim via `juice_director.py`
5. Tracking — attempts, completion codes, CSV export
