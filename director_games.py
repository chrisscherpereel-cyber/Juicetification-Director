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

try:
    import student_store  # shared with the sims; reads completion records
except Exception:  # module or its deps not present → auto-tracking disabled
    student_store = None

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
    publish_config(get_game(new_id))  # so ?game=CODE links can resolve
    return True, new_id


def create_game_from_params(owner_id, app_key, title, params,
                            seed_policy="per_student", fixed_seed=None):
    """Create a game directly from a params dict, without needing a saved
    configuration first (config_id stays null; the snapshot is the source)."""
    title = (title or "").strip()
    if not title:
        return False, "Please give the game a title."
    if seed_policy == "fixed" and not fixed_seed:
        return False, "A fixed-seed game needs a seed number."
    snapshot = json.dumps(params)
    code = _unique_code()
    new_id = db.run_returning_id(
        """INSERT INTO games
           (owner_id, app_key, config_id, config_snapshot, title, join_code,
            status, seed_policy, fixed_seed, created_at)
           VALUES (?, ?, NULL, ?, ?, ?, 'draft', ?, ?, ?)""",
        (owner_id, app_key, snapshot, title, code, seed_policy,
         int(fixed_seed) if fixed_seed else None, db.now_iso()),
    )
    publish_config(get_game(new_id))
    return True, new_id


def short_links_enabled():
    """True when the config store is reachable, so links can be just ?game=CODE."""
    return bool(student_store and student_store.enabled())


def publish_config(game):
    """Publish a game's frozen config to the store, keyed by join code, so a short
    ?game=<code> link resolves. No-op when the store isn't configured."""
    if not short_links_enabled() or not game:
        return False
    try:
        params = json.loads(game["config_snapshot"])
        seed = game.get("fixed_seed") if game.get("seed_policy") == "fixed" else None
        return student_store.save_game_config(
            game["join_code"],
            {"params": params, "seed": seed, "seed_policy": game.get("seed_policy")},
        )
    except Exception:
        return False


def set_status(game_id, status):
    db.run("UPDATE games SET status=? WHERE id=?", (status, game_id))
    if status == "open":
        publish_config(get_game(game_id))  # ensure the short link resolves


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
    sep = "" if base.endswith("/") else "/"
    code = game.get("join_code")

    # Short link: when the config store is reachable, the config lives in Dropbox
    # keyed by join code, so the link only needs ?game=CODE. The sims fetch it.
    if short_links_enabled() and code:
        query = ["game=" + str(code)]
        if section:
            query.append("sec=" + str(section))
        return f"{base}{sep}?" + "&".join(query)

    # Fallback: self-contained link that carries the whole config in the URL.
    params = json.loads(game["config_snapshot"])
    query = []
    if code:
        query.append("game=" + str(code))
    query.append("cfg=" + manifests.encode_cfg(params))
    if game.get("seed_policy") == "fixed" and game.get("fixed_seed"):
        query.append("seed=" + str(game["fixed_seed"]))
    if section:
        query.append("sec=" + str(section))
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


def upsert_attempt(game_id, student_ref, session_id, completion_code=None,
                   score=None):
    """Insert or update an attempt keyed by (game_id, session_id). Used when
    syncing completion records so re-syncing updates rather than duplicates."""
    db.run(
        """INSERT INTO attempts
           (game_id, student_ref, session_id, started_at, completed_at,
            completion_code, score_json)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(game_id, session_id) DO UPDATE SET
             student_ref=excluded.student_ref,
             completed_at=excluded.completed_at,
             completion_code=excluded.completion_code,
             score_json=excluded.score_json""",
        (game_id, student_ref, session_id, db.now_iso(),
         db.now_iso() if completion_code else None, completion_code,
         json.dumps(score) if score is not None else None),
    )


def tracking_available():
    return bool(student_store and student_store.enabled())


def engagement(game):
    """Live per-student engagement for a game, merging progress files with
    completion records. Returns (roster, summary).

    roster: list of {student, status, progress, step, score, last_active}
            status ∈ 'completed' | 'in_progress'
    summary: {started, in_progress, completed}
    Only students who have opened the sim appear (there is no class roster to
    compare against, so 'not started' can't be shown)."""
    if not tracking_available():
        return [], {"started": 0, "in_progress": 0, "completed": 0}
    try:
        progress = student_store.list_progress(game["join_code"])
        completions = student_store.list_completions(game["join_code"])
    except Exception:
        return [], {"started": 0, "in_progress": 0, "completed": 0}

    done = {}
    for c in completions:
        s = c.get("student")
        if s:
            done[s] = c

    by_student = {}
    for p in progress:
        s = p.get("student")
        if not s:
            continue
        by_student[s] = {
            "student": s,
            "progress": p.get("progress"),
            "step": p.get("step"),
            "score": p.get("score"),
            "last_active": p.get("updated_at"),
        }
    # fold in completions (a student may have a completion but be pruned progress)
    for s, c in done.items():
        row = by_student.setdefault(s, {"student": s, "progress": None, "step": None,
                                        "score": None, "last_active": None})
        row["score"] = c.get("score", row.get("score"))

    roster = []
    for s, row in by_student.items():
        is_done = s in done or (row.get("progress") is not None and row["progress"] >= 1.0)
        row["status"] = "completed" if is_done else "in_progress"
        roster.append(row)
    roster.sort(key=lambda r: (r["status"] != "in_progress", r["student"] or ""))

    completed = sum(1 for r in roster if r["status"] == "completed")
    summary = {"started": len(roster),
               "in_progress": len(roster) - completed,
               "completed": completed}
    return roster, summary


def sync_completions(game):
    """Pull completion records from Dropbox for this game and upsert them into the
    attempts roster. Returns (synced_count, error). No-op when unavailable."""
    if not tracking_available():
        return 0, "Automatic tracking isn't configured (needs the Dropbox secrets)."
    try:
        records = student_store.list_completions(game["join_code"])
    except Exception as e:
        return 0, f"Couldn't read completions: {e}"
    n = 0
    for rec in records:
        sid = rec.get("student")
        if not sid:
            continue
        upsert_attempt(game["id"], student_ref=sid, session_id=sid,
                       completion_code=rec.get("completion_code"),
                       score=rec.get("score"))
        n += 1
    return n, None
