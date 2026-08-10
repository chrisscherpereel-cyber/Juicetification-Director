"""
director_db.py — data layer for Juicetification Director.

Plain SQLite over the standard library. Persistence and protection are handled by
`director_storage.py`: the source of truth is an *encrypted* copy of this file in
Dropbox. This module pulls that copy to a local working file before reading and
pushes it back (re-encrypted) after every write. If Dropbox/encryption secrets are
not set, it simply uses the local file (development mode).

All rows are returned as plain dicts. Passwords are hashed upstream; this module
only ever stores hashes.
"""

from __future__ import annotations

import os
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import director_storage as storage

# Local working file. In encrypted-Dropbox mode this is the decrypted copy that
# mirrors the Dropbox blob; in local mode it's the database itself.
DB_PATH = os.environ.get(
    "DIRECTOR_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "director.sqlite"),
)

APPS_SEED = [
    ("spc",  "Squeeze Control",   "https://juicetification-spc.streamlit.app"),
    ("toc",  "Capacity Crush",    "https://juicetification-capacity.streamlit.app"),
    ("app",  "Aggregate Anxiety", "https://juicetification-aggregate.streamlit.app"),
    ("lean", "The Lean Rush",     "https://juicetification-lean.streamlit.app"),
    ("fcst", "Forecast Frenzy",   "https://juicetification-forecasting.streamlit.app"),
]


def backend_name() -> str:
    return storage.backend_name()


def storage_status():
    """(ok, error). Surfaced by the app to explain a misconfiguration clearly."""
    return storage.status()


# Kept for the app's sidebar label.
USE_DROPBOX = storage.ENABLED


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Connection. In encrypted-Dropbox mode we pull the latest copy before opening
# and push the re-encrypted file after a write.
# ---------------------------------------------------------------------------
@contextmanager
def get_conn(write=False):
    storage.ensure_local(DB_PATH)
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    if storage.ENABLED:
        # Rollback journal keeps the DB a single self-contained file after each
        # commit, so it can be encrypted and uploaded whole.
        conn.execute("PRAGMA journal_mode=DELETE;")
    else:
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
        except sqlite3.OperationalError:
            pass
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
    if write:
        storage.push(DB_PATH)


def _rows_to_dicts(cursor):
    if cursor.description is None:
        return []
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def q_all(sql, params=()):
    with get_conn(write=False) as conn:
        return _rows_to_dicts(conn.execute(sql, params))


def q_one(sql, params=()):
    rows = q_all(sql, params)
    return rows[0] if rows else None


def run(sql, params=()):
    with get_conn(write=True) as conn:
        conn.execute(sql, params)


# ---------------------------------------------------------------------------
# Schema — executed statement by statement so it works on both drivers
# (libSQL does not implement executescript).
# ---------------------------------------------------------------------------
STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS instructors (
        id INTEGER PRIMARY KEY,
        email TEXT NOT NULL UNIQUE COLLATE NOCASE,
        display_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'instructor' CHECK (role IN ('admin','instructor')),
        pw_hash TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled')),
        must_change_password INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        last_login_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS apps (
        app_key TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        base_url TEXT NOT NULL,
        schema_version INTEGER NOT NULL DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS app_manifests (
        app_key TEXT NOT NULL REFERENCES apps(app_key),
        schema_version INTEGER NOT NULL,
        manifest_json TEXT NOT NULL,
        synced_at TEXT NOT NULL,
        PRIMARY KEY (app_key, schema_version))""",
    """CREATE TABLE IF NOT EXISTS configurations (
        id INTEGER PRIMARY KEY,
        owner_id INTEGER NOT NULL REFERENCES instructors(id),
        app_key TEXT NOT NULL REFERENCES apps(app_key),
        name TEXT NOT NULL,
        description TEXT,
        params_json TEXT NOT NULL,
        schema_version INTEGER NOT NULL DEFAULT 1,
        version INTEGER NOT NULL DEFAULT 1,
        is_archived INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (owner_id, app_key, name))""",
    """CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY,
        owner_id INTEGER NOT NULL REFERENCES instructors(id),
        app_key TEXT NOT NULL REFERENCES apps(app_key),
        config_id INTEGER REFERENCES configurations(id),
        config_snapshot TEXT NOT NULL,
        title TEXT NOT NULL,
        join_code TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','open','closed')),
        opens_at TEXT,
        closes_at TEXT,
        seed_policy TEXT NOT NULL DEFAULT 'per_student'
            CHECK (seed_policy IN ('per_student','fixed','per_section')),
        fixed_seed INTEGER,
        created_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS launches (
        id INTEGER PRIMARY KEY,
        game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
        label TEXT,
        launch_url TEXT NOT NULL,
        created_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS attempts (
        id INTEGER PRIMARY KEY,
        game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
        student_ref TEXT,
        session_id TEXT,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        completion_code TEXT,
        score_json TEXT,
        UNIQUE (game_id, session_id))""",
    """CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY,
        actor_id INTEGER REFERENCES instructors(id),
        action TEXT NOT NULL,
        target TEXT,
        detail_json TEXT,
        created_at TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS idx_games_owner ON games(owner_id)",
    "CREATE INDEX IF NOT EXISTS idx_games_code ON games(join_code)",
    "CREATE INDEX IF NOT EXISTS idx_attempts_game ON attempts(game_id)",
]


def init_db() -> None:
    """Create tables (idempotent) and seed the apps catalog."""
    with get_conn(write=True) as conn:
        for stmt in STATEMENTS:
            conn.execute(stmt)
        for app_key, name, base_url in APPS_SEED:
            conn.execute(
                """INSERT INTO apps (app_key, name, base_url) VALUES (?, ?, ?)
                   ON CONFLICT(app_key) DO UPDATE SET name=excluded.name""",
                (app_key, name, base_url),
            )


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------
def log_action(actor_id, action, target=None, detail=None) -> None:
    run(
        """INSERT INTO audit_log (actor_id, action, target, detail_json, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (actor_id, action, target,
         json.dumps(detail) if detail is not None else None, now_iso()),
    )


def recent_audit(limit=100):
    return q_all(
        """SELECT a.created_at, a.action, a.target, a.detail_json,
                  i.display_name AS actor
           FROM audit_log a LEFT JOIN instructors i ON i.id = a.actor_id
           ORDER BY a.id DESC LIMIT ?""",
        (limit,),
    )


# ---------------------------------------------------------------------------
# Apps catalog
# ---------------------------------------------------------------------------
def list_apps():
    return q_all("SELECT * FROM apps ORDER BY name")


# ---------------------------------------------------------------------------
# Instructors
# ---------------------------------------------------------------------------
def count_admins() -> int:
    row = q_one(
        "SELECT COUNT(*) AS n FROM instructors WHERE role='admin' AND status='active'"
    )
    return row["n"] if row else 0


def any_admin_exists() -> bool:
    row = q_one("SELECT COUNT(*) AS n FROM instructors WHERE role='admin'")
    return bool(row and row["n"] > 0)


def get_user_by_email(email):
    return q_one(
        "SELECT * FROM instructors WHERE email = ? COLLATE NOCASE", (email.strip(),)
    )


def get_user(user_id):
    return q_one("SELECT * FROM instructors WHERE id = ?", (user_id,))


def list_instructors():
    return q_all(
        """SELECT id, email, display_name, role, status,
                  must_change_password, created_at, last_login_at
           FROM instructors ORDER BY role DESC, display_name COLLATE NOCASE"""
    )


def create_instructor(email, display_name, pw_hash, role="instructor",
                      must_change_password=1):
    """Insert an account. Returns (ok, error_message)."""
    email = email.strip()
    display_name = display_name.strip()
    if not email or "@" not in email:
        return False, "Please enter a valid email address."
    if not display_name:
        return False, "Please enter a display name."
    try:
        run(
            """INSERT INTO instructors
               (email, display_name, role, pw_hash, status,
                must_change_password, created_at)
               VALUES (?, ?, ?, ?, 'active', ?, ?)""",
            (email, display_name, role, pw_hash,
             int(must_change_password), now_iso()),
        )
        return True, None
    except Exception as e:  # unique-violation type differs across drivers
        msg = str(e).lower()
        if "unique" in msg or "constraint" in msg:
            return False, "An account with that email already exists."
        raise


def set_password(user_id, pw_hash, must_change=0):
    run("UPDATE instructors SET pw_hash=?, must_change_password=? WHERE id=?",
        (pw_hash, int(must_change), user_id))


def set_status(user_id, status):
    run("UPDATE instructors SET status=? WHERE id=?", (status, user_id))


def set_role(user_id, role):
    run("UPDATE instructors SET role=? WHERE id=?", (role, user_id))


def delete_instructor(user_id):
    run("DELETE FROM instructors WHERE id=?", (user_id,))


def touch_login(user_id):
    run("UPDATE instructors SET last_login_at=? WHERE id=?", (now_iso(), user_id))
