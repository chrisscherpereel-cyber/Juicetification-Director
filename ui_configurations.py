"""
ui_configurations.py — the Configurations page.

Renders a form straight from each app's manifest, so adding a parameter to an app
means adding one row to director_manifests.py — this UI updates itself. Fields carry
tooltips (definition + student impact), can be filtered to just what differs from the
defaults, and reset to defaults in one click.
"""

from __future__ import annotations

import json

import streamlit as st

import director_db as db
import director_config as config
import director_manifests as manifests
import director_apps as apps_mod


def _widget(app_key, key, spec, current):
    """Render one manifest param as the right Streamlit widget; return its value.
    When the widget's state already exists (e.g. after Reset), we don't pass an
    explicit value so Streamlit uses the state cleanly."""
    label = spec.get("label", key)
    wkey = f"cfg_{app_key}_{key}"
    t = spec["type"]
    help_bits = []
    if spec.get("help"):
        help_bits.append(spec["help"])
    if "min" in spec or "max" in spec:
        help_bits.append(f"(Range {spec.get('min', '−∞')}–{spec.get('max', '∞')}.)")
    if "choices" in spec:
        help_bits.append(f"(Options: {', '.join(str(c) for c in spec['choices'])}.)")
    help_txt = " ".join(help_bits) or None
    has_state = wkey in st.session_state

    if "choices" in spec:
        # A constrained parameter must not be a free text box: juice_director._coerce silently
        # falls back to the default when the typed value isn't an exact match, so a small typo
        # would look accepted and quietly do nothing.
        opts = list(spec["choices"])
        kw = {} if has_state else {"index": opts.index(current) if current in opts else 0}
        return st.selectbox(label, opts, key=wkey, help=help_txt, **kw)
    if t == "bool":
        kw = {} if has_state else {"value": bool(current)}
        return st.checkbox(label, key=wkey, help=help_txt, **kw)
    if t == "int":
        kw = {} if has_state else {"value": int(current)}
        return int(st.number_input(
            label, step=1,
            min_value=int(spec["min"]) if "min" in spec else None,
            max_value=int(spec["max"]) if "max" in spec else None,
            key=wkey, help=help_txt, **kw))
    if t == "float":
        kw = {} if has_state else {"value": float(current)}
        return float(st.number_input(
            label,
            min_value=float(spec["min"]) if "min" in spec else None,
            max_value=float(spec["max"]) if "max" in spec else None,
            key=wkey, help=help_txt, **kw))
    if t == "list":
        kw = {} if has_state else {"value": manifests.list_to_text(current)}
        txt = st.text_input(label, key=wkey,
                            help=(help_txt or "") + " Enter comma-separated values.",
                            **kw)
        return manifests.parse_list_text(txt)
    # str
    kw = {} if has_state else {"value": str(current)}
    return st.text_input(label, key=wkey, help=help_txt, **kw)


def _render_form(app_key, initial, only_changed=False):
    man = apps_mod.get_manifest(app_key)
    values = dict(initial)  # keep hidden fields at their current value
    shown = 0
    for group in manifests.groups(man):
        specs = [(k, s) for k, s in man["params"].items()
                 if s.get("group", "General") == group]
        if only_changed:
            specs = [(k, s) for k, s in specs
                     if initial.get(k, s["default"]) != s["default"]]
        if not specs:
            continue
        st.markdown(f"**{group}**")
        cols = st.columns(2)
        for i, (k, spec) in enumerate(specs):
            with cols[i % 2]:
                values[k] = _widget(app_key, k, spec, initial.get(k, spec["default"]))
                shown += 1
    if only_changed and shown == 0:
        st.caption("Nothing differs from the defaults yet. Turn off "
                   "“only changed” to see every setting.")
    return values


def _reset_to_defaults(app_key):
    man = apps_mod.get_manifest(app_key)
    for k, s in man["params"].items():
        wkey = f"cfg_{app_key}_{k}"
        d = s["default"]
        st.session_state[wkey] = manifests.list_to_text(d) if s["type"] == "list" else d


def render_configurations(user):
    st.header("Configurations")
    st.caption("Set the values a simulation starts with, then save them as a named "
               "preset. Hover any field's ⓘ for what it does and how it changes the "
               "student experience.")

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

    # View controls live OUTSIDE the form (forms allow only submit buttons).
    ctrl_a, ctrl_b = st.columns([2, 1])
    only_changed = ctrl_a.toggle("Show only settings that differ from defaults",
                                 key=f"onlych_{app_key}")
    if ctrl_b.button("↺ Reset all to defaults", key=f"reset_{app_key}",
                     use_container_width=True):
        _reset_to_defaults(app_key)
        st.rerun()

    with st.form(f"config_form_{app_key}"):
        c1, c2 = st.columns([1, 2])
        name = c1.text_input("Configuration name",
                             value=editing["name"] if editing else "")
        desc = c2.text_input("Description (optional)",
                            value=editing["description"] if editing else "")
        st.divider()
        values = _render_form(app_key, initial, only_changed=only_changed)
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
    man = apps_mod.get_manifest(app_key)
    rows = config.list_configs(user["id"], app_key=app_key, include_archived=True)
    if not rows:
        st.caption("None yet for this simulation.")
        return
    for cfg in rows:
        with st.container(border=True):
            top = st.columns([3, 1, 1, 1, 1])
            archived = " · archived" if cfg["is_archived"] else ""
            summary = manifests.summarize_changes(man, config.params_of(cfg))
            top[0].markdown(
                f"**{cfg['name']}**  \n"
                f"<span style='color:gray'>v{cfg['version']}{archived} · "
                f"{cfg['description'] or 'no description'}</span>  \n"
                f"<span style='color:#555'>🎛 {summary}</span>",
                unsafe_allow_html=True)
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
