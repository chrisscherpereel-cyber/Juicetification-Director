"""
director_config.py — CRUD for saved configurations (named parameter presets).

A configuration belongs to one instructor and one app, and stores a full,
validated parameter dict as JSON. Games freeze a copy of this at launch time, so
editing a preset later never disturbs a running class.
"""

from __future__ import annotations

import json

import director_db as db
import director_manifests as manifests


def create_config(owner_id, app_key, name, description, params):
    """Returns (ok, id_or_error)."""
    name = (name or "").strip()
    if not name:
        return False, "Please give the configuration a name."
    man = manifests.get_manifest(app_key)
    if not man:
        return False, f"Unknown app '{app_key}'."
    clean = manifests.validate_params(man, params)
    try:
        new_id = db.run_returning_id(
            """INSERT INTO configurations
               (owner_id, app_key, name, description, params_json,
                schema_version, version, is_archived, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?, ?)""",
            (owner_id, app_key, name, (description or "").strip(),
             json.dumps(clean), man["schema_version"],
             db.now_iso(), db.now_iso()),
        )
        return True, new_id
    except Exception as e:
        if "unique" in str(e).lower() or "constraint" in str(e).lower():
            return False, "You already have a configuration with that name for this app."
        raise


def update_config(config_id, name, description, params):
    cfg = get_config(config_id)
    if not cfg:
        return False, "Configuration not found."
    man = manifests.get_manifest(cfg["app_key"])
    clean = manifests.validate_params(man, params)
    try:
        db.run(
            """UPDATE configurations
               SET name=?, description=?, params_json=?, version=version+1, updated_at=?
               WHERE id=?""",
            ((name or "").strip(), (description or "").strip(),
             json.dumps(clean), db.now_iso(), config_id),
        )
        return True, config_id
    except Exception as e:
        if "unique" in str(e).lower() or "constraint" in str(e).lower():
            return False, "You already have a configuration with that name for this app."
        raise


def duplicate_config(config_id, new_name):
    cfg = get_config(config_id)
    if not cfg:
        return False, "Configuration not found."
    return create_config(cfg["owner_id"], cfg["app_key"], new_name,
                         cfg["description"], json.loads(cfg["params_json"]))


def set_archived(config_id, archived):
    db.run("UPDATE configurations SET is_archived=?, updated_at=? WHERE id=?",
           (1 if archived else 0, db.now_iso(), config_id))


def delete_config(config_id):
    db.run("DELETE FROM configurations WHERE id=?", (config_id,))


def get_config(config_id):
    return db.q_one("SELECT * FROM configurations WHERE id=?", (config_id,))


def list_configs(owner_id, app_key=None, include_archived=False):
    sql = "SELECT * FROM configurations WHERE owner_id=?"
    params = [owner_id]
    if app_key:
        sql += " AND app_key=?"
        params.append(app_key)
    if not include_archived:
        sql += " AND is_archived=0"
    sql += " ORDER BY app_key, name COLLATE NOCASE"
    return db.q_all(sql, tuple(params))


def params_of(cfg):
    """Parsed params dict for a config row."""
    return json.loads(cfg["params_json"]) if cfg else {}
