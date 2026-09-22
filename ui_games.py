"""
ui_games.py — the Games page: create a game from a saved config, get its join
code / launch link / QR, manage status, and track attempts.
"""

from __future__ import annotations

import io
import csv
import json

import streamlit as st

import director_db as db
import director_config as config
import director_games as games
import director_apps as apps_mod
import director_manifests as manifests


_STATUS_BADGE = {"draft": "⚪ draft", "open": "🟢 open", "closed": "🔴 closed"}


def _score_str(score_json):
    if not score_json:
        return "—"
    try:
        import json as _json
        v = _json.loads(score_json)
        return str(v)
    except Exception:
        return str(score_json)


def render_games(user):
    st.header("Games")
    st.caption("Create a class instance from a saved configuration. Students open "
               "the launch link or scan the QR — no login needed on their end.")
    if games.short_links_enabled():
        st.caption("🔗 Short links are on: the config is stored in Dropbox by join "
                   "code, so links are just `…?game=CODE`. (Each sim must fetch by "
                   "code — see the setup note.)")

    _new_game(user)
    st.divider()
    _list_games(user)


def _new_game(user):
    st.subheader("New game")
    apps = [a for a in db.list_apps() if apps_mod.get_manifest(a["app_key"])]
    if not apps:
        st.error("No simulation manifests are registered.")
        return
    app_labels = {f'{a["name"]} ({a["app_key"].upper()})': a["app_key"] for a in apps}
    chosen = st.selectbox("Simulation", list(app_labels.keys()), key="game_app")
    app_key = app_labels[chosen]

    cfgs = config.list_configs(user["id"], app_key=app_key)
    # No need to build a configuration first — "Standard settings" always works.
    source_opts = ["Standard settings"]
    if cfgs:
        source_opts.append("A saved configuration")
    source = st.radio("Settings to use", source_opts, horizontal=True,
                      help="Standard settings run the simulation's built-in defaults. "
                           "To customize, save a preset on the Configurations page.")

    with st.form("new_game"):
        cfg_id = None
        if source == "A saved configuration":
            cfg_labels = {f'{c["name"]} (v{c["version"]})': c["id"] for c in cfgs}
            cfg_label = st.selectbox("Configuration", list(cfg_labels.keys()))
            cfg_id = cfg_labels[cfg_label]
        else:
            st.caption("Every student starts on this simulation's standard settings. "
                       "You can tune them later on the Configurations page.")
        title = st.text_input("Game title", placeholder="MGT 3350 · Sec 001 · Fall 26")
        c1, c2 = st.columns(2)
        seed_policy = c1.selectbox(
            "Scenario seed", ["per_student", "fixed", "per_section"],
            format_func=lambda s: {"per_student": "Unique per student (default)",
                                   "fixed": "Fixed — everyone gets the same",
                                   "per_section": "Per section"}[s])
        fixed_seed = c2.number_input("Fixed seed", min_value=1, value=1000, step=1,
                                     disabled=(seed_policy != "fixed"))
        submitted = st.form_submit_button("Create game", type="primary")
    if submitted:
        seed = fixed_seed if seed_policy == "fixed" else None
        if cfg_id is not None:
            ok, res = games.create_game(user["id"], app_key, cfg_id, title,
                                        seed_policy=seed_policy, fixed_seed=seed)
        else:
            params = manifests.defaults(apps_mod.get_manifest(app_key))
            ok, res = games.create_game_from_params(
                user["id"], app_key, title, params,
                seed_policy=seed_policy, fixed_seed=seed)
        if ok:
            db.log_action(user["id"], "create_game", f"game:{res}")
            st.success("Game created. Open it below to get the link and QR.")
            st.rerun()
        else:
            st.error(res)


def _list_games(user):
    head = st.columns([3, 1])
    head[0].subheader("Your games")
    if head[1].button("🔄 Refresh", key="refresh_games", use_container_width=True,
                      help="Re-pull the latest from storage (games created in other "
                           "sessions or devices)."):
        st.rerun()
    rows = games.list_games(user["id"])
    if not rows:
        st.caption("No games yet.")
        return
    open_n = sum(1 for g in rows if g["status"] == "open")
    st.caption(f"{len(rows)} game(s) · {open_n} open")
    for g in rows:
        badge = _STATUS_BADGE.get(g["status"], g["status"])
        with st.expander(f"{badge} · {g['title']} · {g['app_name']} · "
                         f"code {g['join_code']}"):
            # One misbehaving game must never hide the rest of the list.
            try:
                _game_detail(user, g)
            except Exception as e:
                st.error(f"Couldn't load this game's details: {e}")
                st.caption(f"Join code `{g['join_code']}` · status {g['status']}.")


def _game_detail(user, g):
    url = games.launch_url(g)
    st.markdown(f"**Join code:** `{g['join_code']}`  ·  "
                f"**Config:** {g['config_name'] or '—'}  ·  "
                f"**Seed:** {g['seed_policy']}"
                + (f" ({g['fixed_seed']})" if g['seed_policy'] == 'fixed' else ""))
    # Plain-English summary of what students will experience.
    man = apps_mod.get_manifest(g["app_key"])
    if man:
        try:
            summary = manifests.summarize_changes(man, json.loads(g["config_snapshot"]))
            st.caption(f"🎛 What students get: {summary}")
        except Exception:
            pass
    st.text_input("Launch link", value=url, key=f"url_{g['id']}")
    st.link_button("▶ Open the student view in a new tab", url,
                   use_container_width=True,
                   help="See exactly what a student sees before you share the link.")
    cols = st.columns([1, 2])
    with cols[0]:
        try:
            st.markdown(games.qr_svg(url), unsafe_allow_html=True)
        except Exception:
            st.caption("(QR needs the `qrcode` package.)")
    with cols[1]:
        st.caption("Status")
        s1, s2, s3 = st.columns(3)
        if s1.button("Open", key=f"open_{g['id']}", use_container_width=True):
            games.set_status(g["id"], "open"); st.rerun()
        if s2.button("Close", key=f"close_{g['id']}", use_container_width=True):
            games.set_status(g["id"], "closed"); st.rerun()
        if s3.button("Draft", key=f"draft_{g['id']}", use_container_width=True):
            games.set_status(g["id"], "draft"); st.rerun()
        st.caption("Note: links are self-contained, so 'closed' is an organizational "
                   "label — it doesn't disable an already-shared link.")
        with st.popover("Delete game", use_container_width=True):
            st.warning("Delete this game and its attempt records?")
            if st.button("Yes, delete", key=f"delg_{g['id']}"):
                games.delete_game(g["id"])
                db.log_action(user["id"], "delete_game", f"game:{g['id']}")
                st.rerun()

    st.divider()
    _tracking(g)


def _engagement(g):
    st.markdown("**Live engagement**")
    # Load on demand — reading progress hits Dropbox, so we don't do it for every
    # game on every page render (that made large game lists slow and fragile).
    load_key = f"eng_load_{g['id']}"
    if not st.session_state.get(load_key):
        if st.button("Show live engagement", key=f"showeng_{g['id']}",
                     use_container_width=True):
            st.session_state[load_key] = True
            st.rerun()
        st.caption("Who has started, mid-way, or finished — loaded from storage on "
                   "demand.")
        return
    c1, c2 = st.columns([1, 3])
    if c1.button("🔄 Refresh", key=f"eng_{g['id']}", use_container_width=True):
        st.rerun()
    c2.caption("Read live from each student's progress. Shows students once they "
               "open the sim.")
    try:
        roster, summary = games.engagement(g)
    except Exception as e:
        st.warning(f"Couldn't load engagement right now: {e}")
        st.divider()
        return
    m1, m2, m3 = st.columns(3)
    m1.metric("Started", summary["started"])
    m2.metric("In progress", summary["in_progress"])
    m3.metric("Completed", summary["completed"])
    if roster:
        def _pct(p):
            return f"{round(p * 100)}%" if isinstance(p, (int, float)) else "—"
        st.dataframe(
            [{"Student": r["student"] or "—",
              "Status": "✅ done" if r["status"] == "completed" else "⏳ in progress",
              "Progress": _pct(r.get("progress")),
              "Step": r.get("step") or "—",
              "Score": _score_str(json.dumps(r["score"]) if r.get("score") is not None else None),
              "Last active": r.get("last_active") or "—"} for r in roster],
            use_container_width=True, hide_index=True)
    else:
        st.caption("No students have opened this game yet.")
    st.divider()


def _tracking(g):
    if games.tracking_available():
        _engagement(g)

    st.markdown("**Attempts / completion tracking**")

    # Automatic sync from Dropbox completion records, when configured.
    if games.tracking_available():
        cols = st.columns([1, 2])
        if cols[0].button("🔄 Sync completions", key=f"sync_{g['id']}",
                          use_container_width=True):
            n, err = games.sync_completions(g)
            if err:
                st.error(err)
            else:
                st.success(f"Synced {n} completion record(s) from Dropbox.")
            st.rerun()
        cols[1].caption("Pulls each student's completion record (written when they "
                        "finish the sim) into the roster below. Re-syncing updates "
                        "existing rows rather than duplicating.")
    else:
        st.caption("Record completions manually below. (Automatic sync activates "
                   "once the Dropbox + encryption secrets are set and the sims use "
                   "student_store.)")

    attempts = games.list_attempts(g["id"])
    if attempts:
        st.dataframe(
            [{"Student": a["student_ref"] or "—", "Session": a["session_id"] or "—",
              "Completion code": a["completion_code"] or "—",
              "Score": _score_str(a.get("score_json")),
              "Recorded": a["started_at"]} for a in attempts],
            use_container_width=True, hide_index=True)
        # CSV export
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["student_ref", "session_id", "completion_code", "score",
                    "recorded_at"])
        for a in attempts:
            w.writerow([a["student_ref"] or "", a["session_id"] or "",
                        a["completion_code"] or "", _score_str(a.get("score_json")),
                        a["started_at"]])
        st.download_button("⬇ Export attempts CSV", data=buf.getvalue(),
                           file_name=f"{g['join_code']}_attempts.csv",
                           mime="text/csv", key=f"csv_{g['id']}")
    else:
        st.caption("No attempts recorded yet.")

    with st.form(f"add_attempt_{g['id']}", clear_on_submit=True):
        a1, a2, a3 = st.columns(3)
        sref = a1.text_input("Student (name or id)")
        sess = a2.text_input("Session id")
        code = a3.text_input("Completion code")
        if st.form_submit_button("Record attempt"):
            ok, err = games.add_attempt(g["id"], sref, sess, code, completed=bool(code))
            if ok:
                st.rerun()
            else:
                st.error(err)
