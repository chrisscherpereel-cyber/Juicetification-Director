"""
director_apps.py — administrator management of the app catalog.

The Grand Director can rename apps, change their URLs, add new simulations, and
provide a parameter schema (manifest) for an app so it becomes usable in
Configurations and Games.

Manifest resolution order for any app_key:
  1. an admin-provided manifest stored in `app_manifests` (highest version wins)
  2. the built-in manifest in `director_manifests.py`
So a new app becomes fully functional the moment the admin pastes a valid manifest,
and an admin can also override a built-in schema.
"""

from __future__ import annotations

import re
import json

import director_db as db
import director_manifests as builtin

_KEY_RE = re.compile(r"^[a-z0-9_]{2,20}$")
_ALLOWED_TYPES = {"int", "float", "bool", "str", "list"}


# --------------------------------------------------------------------------
# Read
# --------------------------------------------------------------------------
def list_apps():
    return db.list_apps()


def get_app(app_key):
    return db.get_app(app_key)


def get_manifest(app_key):
    """Admin-provided manifest if present, else the built-in one, else None."""
    row = db.q_one(
        """SELECT manifest_json FROM app_manifests WHERE app_key=?
           ORDER BY schema_version DESC LIMIT 1""",
        (app_key,),
    )
    if row:
        try:
            return json.loads(row["manifest_json"])
        except Exception:
            pass
    return builtin.get_manifest(app_key)


def has_manifest(app_key):
    return get_manifest(app_key) is not None


def manifest_source(app_key):
    if db.q_one("SELECT 1 FROM app_manifests WHERE app_key=?", (app_key,)):
        return "custom"
    if builtin.get_manifest(app_key):
        return "built-in"
    return "none"


def usage(app_key):
    """(config_count, game_count) referencing this app."""
    c = db.q_one("SELECT COUNT(*) n FROM configurations WHERE app_key=?", (app_key,))
    g = db.q_one("SELECT COUNT(*) n FROM games WHERE app_key=?", (app_key,))
    return (c["n"] if c else 0), (g["n"] if g else 0)


# --------------------------------------------------------------------------
# Validate a manifest payload
# --------------------------------------------------------------------------
def validate_manifest(app_key, manifest):
    """Return (ok, normalized_manifest, error). Accepts a dict or a JSON string."""
    if isinstance(manifest, str):
        manifest = manifest.strip()
        if not manifest:
            return False, None, "Manifest is empty."
        try:
            manifest = json.loads(manifest)
        except Exception as e:
            return False, None, f"Not valid JSON: {e}"
    if not isinstance(manifest, dict):
        return False, None, "Manifest must be a JSON object."
    params = manifest.get("params")
    if not isinstance(params, dict) or not params:
        return False, None, "Manifest needs a non-empty 'params' object."
    for key, spec in params.items():
        if not isinstance(spec, dict):
            return False, None, f"Param '{key}' must be an object."
        t = spec.get("type")
        if t not in _ALLOWED_TYPES:
            return False, None, (f"Param '{key}' has type '{t}'. Allowed: "
                                 f"{', '.join(sorted(_ALLOWED_TYPES))}.")
        if "default" not in spec:
            return False, None, f"Param '{key}' needs a 'default'."
    # normalize identity fields
    manifest["app_key"] = app_key
    manifest.setdefault("name", get_app(app_key)["name"] if get_app(app_key) else app_key)
    manifest.setdefault("schema_version", 1)
    return True, manifest, None


# --------------------------------------------------------------------------
# Write
# --------------------------------------------------------------------------
def create_app(app_key, name, base_url, manifest=None):
    app_key = (app_key or "").strip().lower()
    name = (name or "").strip()
    base_url = (base_url or "").strip()
    if not _KEY_RE.match(app_key):
        return False, "Key must be 2–20 chars: lowercase letters, digits, underscore."
    if db.get_app(app_key):
        return False, "That app key already exists."
    if not name:
        return False, "Please enter a display name."
    db.run("INSERT INTO apps (app_key, name, base_url, schema_version) VALUES (?, ?, ?, 1)",
           (app_key, name, base_url))
    if manifest:
        ok, err = set_manifest(app_key, manifest)
        if not ok:
            return True, f"App added, but the manifest wasn't saved: {err}"
    return True, None


def update_app(app_key, name, base_url):
    name = (name or "").strip()
    if not name:
        return False, "Please enter a display name."
    if not db.get_app(app_key):
        return False, "App not found."
    db.run("UPDATE apps SET name=?, base_url=? WHERE app_key=?",
           (name, (base_url or "").strip(), app_key))
    return True, None


def set_manifest(app_key, manifest):
    ok, man, err = validate_manifest(app_key, manifest)
    if not ok:
        return False, err
    sv = int(man.get("schema_version", 1))
    db.run(
        """INSERT INTO app_manifests (app_key, schema_version, manifest_json, synced_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(app_key, schema_version)
           DO UPDATE SET manifest_json=excluded.manifest_json,
                         synced_at=excluded.synced_at""",
        (app_key, sv, json.dumps(man), db.now_iso()),
    )
    return True, None


def clear_manifest(app_key):
    """Remove admin manifest override (falls back to built-in, if any)."""
    db.run("DELETE FROM app_manifests WHERE app_key=?", (app_key,))


def delete_app(app_key):
    n_cfg, n_game = usage(app_key)
    if n_cfg or n_game:
        return False, (f"Can't delete: {n_cfg} configuration(s) and {n_game} game(s) "
                       "still use this app. Remove those first.")
    db.run("DELETE FROM app_manifests WHERE app_key=?", (app_key,))
    db.run("DELETE FROM apps WHERE app_key=?", (app_key,))
    return True, None
