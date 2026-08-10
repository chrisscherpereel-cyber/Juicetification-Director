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
| `director_db.py` | SQLite data layer + CRUD (uses the storage layer) |
| `director_storage.py` | Encrypts the DB and syncs it to Dropbox |
| `director_auth.py` | PBKDF2 password hashing & verification |
| `requirements.txt` | `streamlit`, `dropbox`, `cryptography` |
| `.streamlit/secrets.toml.example` | Template for your key + Dropbox credentials |
| `.gitignore` | Keeps the DB file and secrets out of git |
| `director.sqlite` | Local working copy (decrypted); the real copy lives in Dropbox |

## Run locally

```bash
cd "Juicetification Director"
pip install -r requirements.txt
streamlit run director_app.py
```

Open the URL Streamlit prints, then create your Grand Director account.

## Persistence: encrypted SQLite in Dropbox

The database is a normal SQLite file, but its **source of truth is an encrypted
copy in your Dropbox**. On start the app downloads and decrypts it to a local
working file; after every write it re-encrypts the file and uploads it. Encryption
is Fernet (AES-128-CBC + HMAC), so the file in Dropbox is unreadable and
tamper-evident without your key.

Mode is chosen automatically:

- **No secrets set →** local file `director.sqlite` only. Fine for development, but
  on cloud hosting it resets when the app rebuilds or sleeps.
- **Key + Dropbox secrets set →** encrypted file in Dropbox. Instructors and all
  data **persist** across restarts.

The sidebar shows which mode is active (“🔒 … persistent” vs. “not persistent”).

> **Single-writer design.** One synced file assumes about one writer at a time.
> That fits this app: only the administrator and instructors ever write, and rarely
> — students never touch this database. Run the Director as a single Streamlit app
> to avoid two instances overwriting each other.

### One-time setup

**1. Make an encryption key** (keep it safe — lose it and the Dropbox copy can't be
decrypted):

```bash
python -c "from director_storage import generate_key; print(generate_key())"
```

**2. Create a Dropbox app** at <https://www.dropbox.com/developers/apps> → *Scoped
access* → *App folder* (simplest) → enable `files.content.read` and
`files.content.write`. Note the **App key** and **App secret**.

**3. Get a refresh token** (never expires). Visit this URL in a browser (replace
`APP_KEY`), approve, copy the code:

```
https://www.dropbox.com/oauth2/authorize?client_id=APP_KEY&response_type=code&token_access_type=offline
```

Then exchange the code once:

```bash
curl https://api.dropboxapi.com/oauth2/token \
  -d code=PASTE_CODE -d grant_type=authorization_code \
  -u APP_KEY:APP_SECRET
```

The JSON response contains `refresh_token`.

**4. Put the values in secrets** — locally copy `.streamlit/secrets.toml.example`
to `.streamlit/secrets.toml` (git-ignored) and fill in; on Streamlit Community
Cloud paste the same lines into **App → Settings → Secrets**:
`DB_ENCRYPTION_KEY`, `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`,
`DROPBOX_REFRESH_TOKEN`, and optionally `DROPBOX_DB_PATH`.

No schema step — the app creates its tables and the first encrypted file on first
run.

## Deploy on Streamlit Community Cloud

Push this folder to a repo, point a new Streamlit app at `director_app.py`, and add
the secrets above. `requirements.txt` includes `dropbox` and `cryptography`, both of
which install from prebuilt wheels — no compiler needed. If a package is missing or
a secret is malformed, the app shows a clear message instead of crashing.

**Do not commit** `director.sqlite` or `.streamlit/secrets.toml` — both are already
in `.gitignore`.

## Security notes (protected information)

- Passwords are never stored in clear — only PBKDF2-HMAC-SHA256 hashes with a
  per-user salt and 200,000 iterations.
- The database file is **encrypted at rest in Dropbox** with authenticated
  encryption (Fernet/AES); a tampered file is rejected on decrypt.
- The encryption key and Dropbox credentials live only in Streamlit secrets, never
  in Dropbox and never in git (`.gitignore` covers `secrets.toml` and the DB file).
- Email uniqueness is case-insensitive.
- All database access uses parameterized queries.
- Set a strong Grand Director password; that account controls the whole system.

## Roadmap (from the plan)

1. ✅ Foundation + access control (this build)
2. Configurations — schema-driven forms per app, saved as named presets
3. Games — bind a config to a class, mint a join code, launch links + QR
4. Wire the join code into each sim via `juice_director.py`
5. Tracking — attempts, completion codes, CSV export
