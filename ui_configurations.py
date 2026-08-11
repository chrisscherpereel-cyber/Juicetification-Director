"""
ui_configurations.py — the Configurations page.

Renders a form straight from each app's manifest, so adding a parameter to an app
means adding one row to director_manifests.py — this UI updates itself.
"""

from __future__ import annotations

import json

import streamlit as st

import director_db as db
import director_config as config
import director_manifests as manifests
import director_apps as apps_mod


def _widget(app_key, key, spec, current):
    """Render one manifest param as the right Streamlit widget; return its value."""
    label = spec.get("label", key)
    wkey = f"cfg_{app_key}_{key}"
    t = spec["type"]
    help_bits = []
    if "min" in spec or "max" in spec:
        help_bits.append(f"range {spec.get('min', '−∞')}–{spec.get('max', '∞')}")
    help_txt = "; ".join(help_bits) or None

    if t == "bool":
        return st.checkbox(label, value=bool(current), key=wkey, help=help_txt)
    if t == "int":
        return int(st.number_input(
            label, value=int(current), step=1,
            min_value=int(spec["min"]) if "min" in spec else None,
            max_value=int(spec["max"]) if "max" in spec else None,
            key=wkey, help=help_txt))
    if t == "float":
        return float(st.number_input(
            label, value=float(current),
            min_value=float(spec["min"]) if "min" in spec else None,
            max_value=float(spec["max"]) if "max" in spec else None,
            key=wkey, help=help_txt))
    if t == "list":
        txt = st.text_input(label, value=manifests.list_to_text(current),
                            key=wkey, help="comma-separated values")
        return manifests.parse_list_text(txt)
    # str
    return st.text_input(label, value=str(current), key=wkey, help=help_txt)


def _render_form(app_key, initial):
    man = apps_mod.get_manifest(app_key)
    values = {}
    for group in manifests.groups(man):
        st.markdown(f"**{group}**")
        specs = [(k, s) for k, s in man["params"].items()
                 if s.get("group", "General") == group]
        cols = st.columns(2)
        for i, (k, spec) in enumerate(specs):
            with cols[i % 2]:
                values[k] = _widget(app_key, k, spec,
                                    initial.get(k, spec["default"]))
    return values


def render_configurations(user):
    st.header("Configurations")
    st.caption("Set the default values each simulation starts with, and save them "
               "as named presets you can reuse across classes.")

    apps = [a for a in db.list_apps() if apps_mod.get_manifest(a["app_key"])]
    if not apps:
        st.error("No simulation manifests are registered.")
        return
    app_labels = {f'{a["name"]} ({a["app_key"].upper()})': a["app_key"] for a in apps}
    chosen_label = st.selectbox("Simulation", list(app_labels.keys()))
    app_key = app_labels[chosen_label]

    editing_id = st.session_state.get("editing_config_id")
    editing = config.get_config(editing_id) if editing_id else None
    if editing and editing["app_key"] != app_key:
        editing = None  # switched apps → drop the edit context
        st.session_state.pop("editing_config_id", None)

    initial = config.params_of(editing) if editing else manifests.defaults(
        apps_mod.get_manifest(app_key))

    st.divider()
    st.subheader("Edit configuration" if editing else "New configuration")
    if editing:
        st.caption(f"Editing **{editing['name']}** (version {editing['version']}). "
                   "Saving bumps the version; running games keep their frozen copy.")

    with st.form(f"config_form_{app_key}"):
        c1, c2 = st.columns([1, 2])
        name = c1.text_input("Configuration name",
                             value=editing["name"] if editing else "")
        desc = c2.text_input("Description (optional)",
                            value=editing["description"] if editing else "")
        st.divider()
        values = _render_form(app_key, initial)
        col_a, col_b = st.columns(2)
        save = col_a.form_submit_button(
            "Save changes" if editing else "Save configuration", type="primary")
        cancel = col_b.form_submit_button("Cancel edit") if editing else False

    if cancel:
        st.session_state.pop("editing_config_id", None)
        st.rerun()

    if save:
        if editing:
            ok, res = config.update_config(editing["id"], name, desc, values)
        else:
            ok, res = config.create_config(user["id"], app_key, name, desc, values)
        if ok:
            db.log_action(user["id"],
                          "update_config" if editing else "create_config",
                          f"config:{res}")
            st.session_state.pop("editing_config_id", None)
            st.success("Saved.")
            st.rerun()
        else:
            st.error(res)

    _render_saved(user, app_key)


def _render_saved(user, app_key):
    st.divider()
    st.subheader("Saved configurations")
    rows = config.list_configs(user["id"], app_key=app_key, include_archived=True)
    if not rows:
        st.caption("None yet for this simulation.")
        return
    for cfg in rows:
        with st.container(border=True):
            top = st.columns([3, 1, 1, 1, 1])
            archived = " · archived" if cfg["is_archived"] else ""
            top[0].markdown(f"**{cfg['name']}**  \n"
                            f"<span style='color:gray'>v{cfg['version']}"
                            f"{archived} · {cfg['description'] or 'no description'}"
                            f"</span>", unsafe_allow_html=True)
            if top[1].button("Edit", key=f"edit_{cfg['id']}", use_container_width=True):
                st.session_state["editing_config_id"] = cfg["id"]
                st.rerun()
            with top[2].popover("Duplicate", use_container_width=True):
                with st.form(f"dup_{cfg['id']}"):
                    nn = st.text_input("New name", value=f"{cfg['name']} (copy)")
                    if st.form_submit_button("Create copy"):
                        ok, res = config.duplicate_config(cfg["id"], nn)
                        if ok:
                            st.success("Duplicated."); st.rerun()
                        else:
                            st.error(res)
            if cfg["is_archived"]:
                if top[3].button("Unarchive", key=f"un_{cfg['id']}",
                                 use_container_width=True):
                    config.set_archived(cfg["id"], False); st.rerun()
            else:
                if top[3].button("Archive", key=f"ar_{cfg['id']}",
                                 use_container_width=True):
                    config.set_archived(cfg["id"], True); st.rerun()
            with top[4].popover("Delete", use_container_width=True):
                st.warning("Delete this configuration permanently?")
                if st.button("Yes, delete", key=f"del_cfg_{cfg['id']}"):
                    config.delete_config(cfg["id"])
                    db.log_action(user["id"], "delete_config", f"config:{cfg['id']}")
                    st.rerun()
            # export
            st.download_button(
                "⬇ Export JSON",
                data=json.dumps({"app_key": cfg["app_key"], "name": cfg["name"],
                                 "params": config.params_of(cfg)}, indent=2),
                file_name=f"{cfg['app_key']}_{cfg['name']}.json",
                mime="application/json", key=f"exp_{cfg['id']}")

    with st.expander("Import a configuration from JSON"):
        up = st.file_uploader("JSON file", type="json", key=f"imp_{app_key}")
        if up is not None:
            try:
                data = json.load(up)
                ok, res = config.create_config(
                    user["id"], app_key, data.get("name", "Imported"),
                    data.get("description", ""), data.get("params", {}))
                if ok:
                    st.success("Imported."); st.rerun()
                else:
                    st.error(res)
            except Exception as e:
                st.error(f"Couldn't read that file: {e}")
