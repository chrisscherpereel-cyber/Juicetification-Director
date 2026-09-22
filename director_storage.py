"""
director_storage.py — encrypted persistence for the Director's SQLite file.

Strategy: keep working with an ordinary local SQLite file, but keep the *source
of truth* as a single **encrypted** blob in Dropbox.

  • On first use in a process, the encrypted blob is downloaded and decrypted to
    the local working file (or, if none exists yet, we start fresh).
  • After every write, the local file is re-encrypted and uploaded, overwriting
    the Dropbox copy.

Encryption is Fernet (AES-128-CBC + HMAC authentication) from the `cryptography`
package, so the file at rest in Dropbox is unreadable and tamper-evident without
your key. The key lives in Streamlit secrets, never in Dropbox and never in git.

Concurrency note: a single synced file assumes roughly one writer at a time. That
is the right fit here — only the administrator and instructors ever write, and
those actions are infrequent; students never touch this database. Simultaneous
writes from two separate app instances could still last-write-win, so run the
Director as a single Streamlit app.

If Dropbox/encryption secrets are not configured, everything here becomes a no-op
and the app simply uses the local file (development mode).
"""

from __future__ import annotations

import os
import threading

# ---------------------------------------------------------------------------
# Configuration (environment first, then Streamlit secrets)
# ---------------------------------------------------------------------------
def _cfg(name, default=None):
    val = os.environ.get(name)
    if val:
        return val
    try:
        import streamlit as st
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return default


DB_ENCRYPTION_KEY   = _cfg("DB_ENCRYPTION_KEY")
DROPBOX_DB_PATH     = _cfg("DROPBOX_DB_PATH", "/JuicetificationDirector/director.enc")
DROPBOX_REFRESH_TOKEN = _cfg("DROPBOX_REFRESH_TOKEN")
DROPBOX_APP_KEY     = _cfg("DROPBOX_APP_KEY")
DROPBOX_APP_SECRET  = _cfg("DROPBOX_APP_SECRET")
DROPBOX_ACCESS_TOKEN = _cfg("DROPBOX_ACCESS_TOKEN")  # optional simple/legacy mode

_have_dropbox_creds = bool(
    (DROPBOX_REFRESH_TOKEN and DROPBOX_APP_KEY and DROPBOX_APP_SECRET)
    or DROPBOX_ACCESS_TOKEN
)
ENABLED = bool(DB_ENCRYPTION_KEY and _have_dropbox_creds)

_lock = threading.Lock()
_pulled = False


def backend_name() -> str:
    return "Encrypted SQLite in Dropbox" if ENABLED else "Local SQLite file"


def status():
    """(ok, error_message). Explains a misconfiguration instead of crashing."""
    if not ENABLED:
        # Half-configured? Point out exactly what's missing so it's obvious.
        if DB_ENCRYPTION_KEY and not _have_dropbox_creds:
            return False, ("DB_ENCRYPTION_KEY is set but Dropbox credentials are "
                           "missing (need DROPBOX_REFRESH_TOKEN + DROPBOX_APP_KEY + "
                           "DROPBOX_APP_SECRET, or DROPBOX_ACCESS_TOKEN).")
        if _have_dropbox_creds and not DB_ENCRYPTION_KEY:
            return False, "Dropbox credentials are set but DB_ENCRYPTION_KEY is missing."
        return True, None  # fully local mode, that's fine
    try:
        import cryptography  # noqa: F401
        import dropbox       # noqa: F401
    except Exception as e:
        return False, (f"Encrypted-Dropbox mode is configured but a required package "
                       f"isn't installed: {e}")
    try:
        _fernet()
    except Exception as e:
        return False, f"DB_ENCRYPTION_KEY is invalid: {e}"
    return True, None


# ---------------------------------------------------------------------------
# Encryption
# ---------------------------------------------------------------------------
def _fernet():
    from cryptography.fernet import Fernet
    key = DB_ENCRYPTION_KEY
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def generate_key() -> str:
    """Utility for one-time key creation (see README)."""
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


# ---------------------------------------------------------------------------
# Remote (Dropbox) — isolated so tests can swap it for an in-memory store.
# ---------------------------------------------------------------------------
def _client():
    import dropbox
    if DROPBOX_REFRESH_TOKEN:
        return dropbox.Dropbox(
            oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
            app_key=DROPBOX_APP_KEY,
            app_secret=DROPBOX_APP_SECRET,
        )
    return dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)


def _remote_download():
    """Return the ciphertext bytes stored in Dropbox, or None if absent."""
    import dropbox
    try:
        _md, res = _client().files_download(DROPBOX_DB_PATH)
        return res.content
    except dropbox.exceptions.ApiError:
        return None  # not created yet → fresh start


def _remote_upload(ciphertext: bytes):
    import dropbox
    _client().files_upload(
        ciphertext, DROPBOX_DB_PATH,
        mode=dropbox.files.WriteMode.overwrite,
    )


# ---------------------------------------------------------------------------
# Public API used by director_db.py
# ---------------------------------------------------------------------------
def mark_stale():
    """Force the next ensure_local to re-pull from Dropbox. Call once at the start
    of each app interaction so reads reflect changes made in other sessions."""
    global _pulled
    _pulled = False


def ensure_local(db_path: str, force: bool = False):
    """Make sure the local working file reflects the encrypted Dropbox copy.
    No-op in local mode. Pulls when stale (or `force=True`, used right before a
    write so the change is applied on top of the latest Dropbox state rather than a
    stale local copy — this prevents overwriting games created in other sessions)."""
    global _pulled
    if not ENABLED:
        return
    if not force and _pulled and os.path.exists(db_path):
        return
    with _lock:
        if not force and _pulled and os.path.exists(db_path):
            return
        ciphertext = _remote_download()
        if ciphertext is not None:
            data = _fernet().decrypt(ciphertext)
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
            with open(db_path, "wb") as f:
                f.write(data)
        # if None: leave absent so the DB layer creates a fresh schema locally
        _pulled = True


def push(db_path: str):
    """Encrypt the local file and upload it, overwriting the Dropbox copy.
    No-op in local mode. Called after writes."""
    if not ENABLED:
        return
    if not os.path.exists(db_path):
        return
    with _lock:
        with open(db_path, "rb") as f:
            raw = f.read()
        _remote_upload(_fernet().encrypt(raw))


def _reset_for_tests():
    global _pulled
    _pulled = False
