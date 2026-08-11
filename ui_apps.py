"""
ui_apps.py — the Applications page (Grand Director only).

Rename simulations, change their URLs, add new simulations, and give an app a
parameter schema (manifest) so it can be configured and run.
"""

from __future__ import annotations

import json

import streamlit as st

import director_db as db
import director_apps as apps_mod


def render_applications(user):
    st.header("Applications")
    st.caption("Rename the simulations, change their links, add new ones, or give a "
               "new app its parameter schema. Only the Grand Director sees this page.")

    _overview()
    st.divider()
    _edit_existing()
    st.divider()
    _add_new()


def _overview():
    rows = apps_mod.list_apps()
    table = []
    for a in rows:
        n_cfg, n_game = apps_mod.usage(a["app_key"])
        table.append({
            "Name": a["name"],
            "Key": a["app_key"],
            "URL": a["base_url"],
            "Schema": apps_mod.manifest_source(a["app_key"]),
            "Configs": n_cfg,
            "Games": n_game,
        })
    st.dataframe(table, use_container_width=True, hide_index=True)


def _edit_existing():
    st.subheader("Edit an application")
    apps = apps_mod.list_apps()
    if not apps:
        st.caption("No applications yet.")
        return
    labels = {f'{a["name"]} ({a["app_key"]})': a["app_key"] for a in apps}
    label = st.selectbox("Application", list(labels.keys()))
    app_key = labels[label]
    app = apps_mod.get_app(app_key)

    with st.form(f"edit_app_{app_key}"):
        name = st.text_input("Display name", value=app["name"])
        base_url = st.text_input("Base URL", value=app["base_url"])
        saved = st.form_submit_button("Save changes", type="primary")
    if saved:
        ok, err = apps_mod.update_app(app_key, name, base_url)
        if ok:
            db.log_action(user["id"], "update_app", f"app:{app_key}")
            st.success("Saved."); st.rerun()
        else:
            st.error(err)

    # Manifest editor
    with st.expander("Parameter schema (manifest)"):
        source = apps_mod.manifest_source(app_key)
        st.caption(f"Current source: **{source}**. "
                   "This JSON defines the fields instructors set in Configurations.")
        current = apps_mod.get_manifest(app_key)
        text = json.dumps(current, indent=2) if current else _manifest_template(app_key)
        edited = st.text_area("Manifest JSON", value=text, height=320,
                              key=f"man_{app_key}")
        c1, c2 = st.columns(2)
        if c1.button("Save manifest", key=f"savman_{app_key}", type="primary"):
            ok, err = apps_mod.set_manifest(app_key, edited)
            if ok:
                db.log_action(user["id"], "set_manifest", f"app:{app_key}")
                st.success("Manifest saved."); st.rerun()
            else:
                st.error(err)
        if source == "custom":
            if c2.button("Revert to built-in", key=f"revman_{app_key}"):
                apps_mod.clear_manifest(app_key)
                db.log_action(user["id"], "clear_manifest", f"app:{app_key}")
                st.rerun()

    # Delete (guarded)
    n_cfg, n_game = apps_mod.usage(app_key)
    with st.popover("Delete application", use_container_width=True):
        if n_cfg or n_game:
            st.warning(f"In use: {n_cfg} configuration(s), {n_game} game(s). "
                       "Remove those first.")
        else:
            st.warning(f"Delete '{app['name']}' permanently?")
            if st.button("Yes, delete", key=f"delapp_{app_key}"):
                ok, err = apps_mod.delete_app(app_key)
                if ok:
                    db.log_action(user["id"], "delete_app", f"app:{app_key}")
                    st.rerun()
                else:
                    st.error(err)


def _add_new():
    st.subheader("Add a new application")
    with st.form("add_app", clear_on_submit=False):
        c1, c2 = st.columns(2)
        key = c1.text_input("App key", help="2–20 chars: lowercase letters, digits, "
                            "underscore. Stable id used in links; can't change later.")
        name = c2.text_input("Display name")
        base_url = st.text_input("Base URL", placeholder="https://your-app.streamlit.app")
        manifest = st.text_area(
            "Parameter schema (manifest JSON) — optional",
            help="Paste the app's manifest so instructors can configure it. You can "
                 "also add this later. Leave blank to register the app now.",
            height=200)
        submitted = st.form_submit_button("Add application", type="primary")
    if submitted:
        ok, msg = apps_mod.create_app(key, name, base_url,
                                     manifest=manifest.strip() or None)
        if ok:
            db.log_action(user["id"], "create_app", f"app:{key.strip().lower()}")
            st.success(msg or "Application added.")
            st.rerun()
        else:
            st.error(msg)


def _manifest_template(app_key):
    return json.dumps({
        "app_key": app_key,
        "name": (apps_mod.get_app(app_key) or {}).get("name", app_key),
        "schema_version": 1,
        "params": {
            "example_number": {"type": "float", "default": 1.0, "min": 0,
                               "group": "General", "label": "Example number"},
            "example_toggle": {"type": "bool", "default": False,
                               "group": "General", "label": "Example toggle"},
        },
    }, indent=2)
