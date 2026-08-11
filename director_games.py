"""
director_games.py — games, join codes, launch links, and QR.

A game binds one app + a frozen copy of one configuration, has a short join code,
a status, and a seed policy. Launch links are **self-contained**: the config is
encoded into the URL (`?cfg=…`), so the sims need no shared database to read it —
they already accept this via `juice_director.resolve_config`.
"""

from __future__ import annotations

import json
import secrets

import director_db as db
import director_config as config
import director_manifests as manifests

# Crockford-ish base32 without easily-confused characters (no I, L, O, U, 0, 1).
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"


def _new_code(n=5):
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def _unique_code():
    for _ in range(20):
        code = _new_code()
        if not db.q_one("SELECT 1 FROM games WHERE join_code=?", (code,)):
            return code
    # Extremely unlikely; widen the space.
    return _new_code(7)


def create_game(owner_id, app_key, config_id, title,
                seed_policy="per_student", fixed_seed=None,
                opens_at=None, closes_at=None):
    title = (title or "").strip()
    if not title:
        return False, "Please give the game a title."
    cfg = config.get_config(config_id)
    if not cfg or cfg["app_key"] != app_key:
        return False, "Pick a configuration that belongs to this app."
    if seed_policy == "fixed" and not fixed_seed:
        return False, "A fixed-seed game needs a seed number."
    snapshot = cfg["params_json"]  # frozen copy
    code = _unique_code()
    new_id = db.run_returning_id(
        """INSERT INTO games
           (owner_id, app_key, config_id, config_snapshot, title, join_code,
            status, opens_at, closes_at, seed_policy, fixed_seed, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?)""",
        (owner_id, app_key, config_id, snapshot, title, code,
         opens_at, closes_at, seed_policy,
         int(fixed_seed) if fixed_seed else None, db.now_iso()),
    )
    return True, new_id


def set_status(game_id, status):
    db.run("UPDATE games SET status=? WHERE id=?", (status, game_id))


def delete_game(game_id):
    db.run("DELETE FROM games WHERE id=?", (game_id,))


def get_game(game_id):
    return db.q_one("SELECT * FROM games WHERE id=?", (game_id,))


def get_game_by_code(code):
    return db.q_one("SELECT * FROM games WHERE join_code=? COLLATE NOCASE",
                    (code.strip(),))


def list_games(owner_id):
    return db.q_all(
        """SELECT g.*, a.name AS app_name, a.base_url AS base_url,
                  c.name AS config_name
           FROM games g
           JOIN apps a ON a.app_key = g.app_key
           LEFT JOIN configurations c ON c.id = g.config_id
           WHERE g.owner_id=?
           ORDER BY g.created_at DESC""",
        (owner_id,),
    )


def launch_url(game, section=None):
    """Build the self-contained student link for a game row (dict).
    Requires 'base_url' — use a row from list_games or join apps yourself."""
    base = game.get("base_url")
    if not base:
        app = db.get_app(game["app_key"])
        base = app["base_url"] if app else ""
    params = json.loads(game["config_snapshot"])
    query = ["cfg=" + manifests.encode_cfg(params)]
    if game.get("seed_policy") == "fixed" and game.get("fixed_seed"):
        query.append("seed=" + str(game["fixed_seed"]))
    if section:
        query.append("sec=" + str(section))
    sep = "" if base.endswith("/") else "/"
    return f"{base}{sep}?" + "&".join(query)


def qr_svg(url, box_size=8):
    """Return an SVG string for a URL's QR code (no Pillow needed)."""
    import qrcode
    import qrcode.image.svg
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgImage,
                      box_size=box_size, border=2)
    import io
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode("utf-8")


# --- attempt tracking (roster) --------------------------------------------
def add_attempt(game_id, student_ref=None, session_id=None,
                completion_code=None, completed=False):
    try:
        db.run(
            """INSERT INTO attempts
               (game_id, student_ref, session_id, started_at, completed_at,
                completion_code)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (game_id, (student_ref or "").strip() or None,
             (session_id or "").strip() or None, db.now_iso(),
             db.now_iso() if completed else None,
             (completion_code or "").strip() or None),
        )
        return True, None
    except Exception as e:
        if "unique" in str(e).lower() or "constraint" in str(e).lower():
            return False, "That session id is already recorded for this game."
        raise


def list_attempts(game_id):
    return db.q_all("SELECT * FROM attempts WHERE game_id=? ORDER BY id", (game_id,))


def delete_attempt(attempt_id):
    db.run("DELETE FROM attempts WHERE id=?", (attempt_id,))
