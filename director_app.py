"""
Juicetification Director — control app for the five operations-management sims.

This build covers the foundation and access control:
  • first-run creation of the Grand Director (administrator)
  • login / logout, forced password change on temp passwords
  • administrator console: add, disable/enable, reset, promote/demote, remove
    instructors (with the last-admin guard)
  • instructor dashboard placeholder for the Configurations / Games phases

Run:  streamlit run director_app.py
"""

from __future__ import annotations

import streamlit as st

import director_db as db
import director_auth as auth
import director_config as config
import director_games as games
import ui_configurations
import ui_games
import ui_apps

st.set_page_config(page_title="Juicetification Director", page_icon="🧃",
                   layout="centered")

_STATUS = {"draft": "⚪", "open": "🟢", "closed": "🔴"}

# ----------------------------------------------------------------------------
# Session helpers
# ----------------------------------------------------------------------------
def current_user():
    return st.session_state.get("auth_user")


def sign_in(user_row):
    st.session_state["auth_user"] = {
        "id": user_row["id"],
        "email": user_row["email"],
        "name": user_row["display_name"],
        "role": user_row["role"],
    }
    db.touch_login(user_row["id"])


def sign_out():
    st.session_state.pop("auth_user", None)
    st.rerun()


def is_admin() -> bool:
    u = current_user()
    return bool(u and u["role"] == "admin")


# ----------------------------------------------------------------------------
# Screens
# ----------------------------------------------------------------------------
def screen_first_run():
    st.title("🧃 Juicetification Director")
    st.subheader("Set up the Grand Director")
    st.caption(
        "No administrator exists yet. Create the top-level account that will "
        "grant access to instructors. Keep these credentials safe — this account "
        "controls the whole system."
    )
    with st.form("first_run"):
        name = st.text_input("Your name", placeholder="e.g. Dr. Chris Scherpereel")
        email = st.text_input("Email (this is your login)",
                              placeholder="you@nau.edu")
        pw = st.text_input("Password", type="password",
                           placeholder="at least 8 characters")
        pw2 = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create administrator", type="primary")
    if submitted:
        problem = auth.password_problem(pw, pw2)
        if problem:
            st.error(problem)
            return
        ok, err = db.create_instructor(
            email, name, auth.hash_password(pw),
            role="admin", must_change_password=0,
        )
        if not ok:
            st.error(err)
            return
        user = db.get_user_by_email(email)
        db.log_action(user["id"], "create_admin", f"instructor:{user['id']}",
                      {"bootstrap": True})
        sign_in(user)
        st.success("Administrator created. Welcome!")
        st.rerun()


def screen_login():
    st.title("🧃 Juicetification Director")
    st.caption("Sign in to manage your simulations.")
    with st.form("login"):
        email = st.text_input("Email", placeholder="you@nau.edu")
        pw = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")
    if submitted:
        user = db.get_user_by_email(email)
        if not user or not auth.verify_password(pw, user["pw_hash"]):
            st.error("Incorrect email or password.")
            return
        if user["status"] != "active":
            st.error("This account has been disabled. Contact your administrator.")
            return
        sign_in(user)
        db.log_action(user["id"], "login", f"instructor:{user['id']}")
        st.rerun()


def screen_force_password_change():
    u = current_user()
    st.title("🧃 Juicetification Director")
    st.subheader("Choose a new password")
    st.caption("Your account was set up with a temporary password. "
               "Please set your own before continuing.")
    with st.form("force_pw"):
        pw = st.text_input("New password", type="password")
        pw2 = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button("Save password", type="primary")
    if submitted:
        problem = auth.password_problem(pw, pw2)
        if problem:
            st.error(problem)
            return
        db.set_password(u["id"], auth.hash_password(pw), must_change=0)
        db.log_action(u["id"], "change_password", f"instructor:{u['id']}")
        st.success("Password updated.")
        st.rerun()


# ----------------------------------------------------------------------------
# Admin console
# ----------------------------------------------------------------------------
def admin_add_instructor():
    st.markdown("#### Add an instructor")
    with st.form("add_instructor", clear_on_submit=True):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name")
        email = c2.text_input("Email")
        c3, c4 = st.columns(2)
        role = c3.selectbox("Role", ["instructor", "admin"],
                            help="Admins can manage other instructors.")
        temp_pw = c4.text_input("Temporary password", type="password",
                                help="They'll be asked to change it at first login.")
        submitted = st.form_submit_button("Create account", type="primary")
    if submitted:
        problem = auth.password_problem(temp_pw)
        if problem:
            st.error(problem)
            return
        ok, err = db.create_instructor(
            email, name, auth.hash_password(temp_pw),
            role=role, must_change_password=1,
        )
        if not ok:
            st.error(err)
            return
        created = db.get_user_by_email(email)
        db.log_action(current_user()["id"], "create_instructor",
                      f"instructor:{created['id']}", {"role": role})
        st.success(f"Created {role} account for {name} ({email}). "
                   "Share the temporary password with them securely.")


def admin_manage_instructors():
    st.markdown("#### Manage instructors")
    people = db.list_instructors()

    # Summary table
    table = [{
        "Name": p["display_name"],
        "Email": p["email"],
        "Role": "Grand Director" if p["role"] == "admin" else "Instructor",
        "Status": p["status"],
        "Last login": p["last_login_at"] or "—",
    } for p in people]
    st.dataframe(table, use_container_width=True, hide_index=True)

    me = current_user()
    admin_count = db.count_admins()

    options = {f'{p["display_name"]} · {p["email"]}': p for p in people}
    label = st.selectbox("Select an account to manage", list(options.keys()))
    target = options[label]
    t_is_self = target["id"] == me["id"]
    t_is_admin = target["role"] == "admin"
    t_active = target["status"] == "active"
    last_active_admin = t_is_admin and t_active and admin_count <= 1

    c1, c2, c3, c4 = st.columns(4)

    # Enable / disable
    if t_active:
        disabled = t_is_self or last_active_admin
        if c1.button("Disable", disabled=disabled, use_container_width=True,
                     help="Can't disable yourself or the last admin"
                     if disabled else None):
            db.set_status(target["id"], "disabled")
            db.log_action(me["id"], "disable_instructor", f'instructor:{target["id"]}')
            st.rerun()
    else:
        if c1.button("Enable", use_container_width=True):
            db.set_status(target["id"], "active")
            db.log_action(me["id"], "enable_instructor", f'instructor:{target["id"]}')
            st.rerun()

    # Promote / demote
    if t_is_admin:
        disabled = last_active_admin or t_is_self
        if c2.button("Make instructor", disabled=disabled, use_container_width=True,
                     help="Can't demote yourself or the last admin"
                     if disabled else None):
            db.set_role(target["id"], "instructor")
            db.log_action(me["id"], "demote", f'instructor:{target["id"]}')
            st.rerun()
    else:
        if c2.button("Make admin", use_container_width=True):
            db.set_role(target["id"], "admin")
            db.log_action(me["id"], "promote", f'instructor:{target["id"]}')
            st.rerun()

    # Reset password
    with c3.popover("Reset password", use_container_width=True):
        with st.form(f"reset_{target['id']}"):
            new_pw = st.text_input("Temporary password", type="password")
            if st.form_submit_button("Set"):
                problem = auth.password_problem(new_pw)
                if problem:
                    st.error(problem)
                else:
                    db.set_password(target["id"], auth.hash_password(new_pw),
                                    must_change=1)
                    db.log_action(me["id"], "reset_password",
                                  f'instructor:{target["id"]}')
                    st.success("Temporary password set. They'll change it at login.")

    # Delete
    delete_disabled = t_is_self or last_active_admin
    with c4.popover("Remove", use_container_width=True,
                    disabled=delete_disabled):
        st.warning(f"Remove {target['display_name']} permanently?")
        if st.button("Yes, remove", key=f"del_{target['id']}"):
            db.delete_instructor(target["id"])
            db.log_action(me["id"], "delete_instructor", f'instructor:{target["id"]}')
            st.rerun()


def admin_audit():
    with st.expander("Activity log"):
        rows = db.recent_audit(100)
        if not rows:
            st.caption("No activity yet.")
        else:
            st.dataframe(
                [{"When": r["created_at"], "Who": r["actor"] or "—",
                  "Action": r["action"], "Target": r["target"] or ""}
                 for r in rows],
                use_container_width=True, hide_index=True,
            )


def screen_admin_console():
    st.header("Administrator console")
    st.caption("Grant and manage access for instructors.")
    admin_add_instructor()
    st.divider()
    admin_manage_instructors()
    st.divider()
    admin_audit()


# ----------------------------------------------------------------------------
# Instructor dashboard (placeholder for later phases)
# ----------------------------------------------------------------------------
def screen_dashboard():
    u = current_user()
    st.header(f"Welcome, {u['name'].split()[0] if u['name'] else 'there'}")

    my_configs = config.list_configs(u["id"])
    my_games = games.list_games(u["id"])
    open_games = [g for g in my_games if g["status"] == "open"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Saved configurations", len(my_configs))
    m2.metric("Games", len(my_games))
    m3.metric("Open now", len(open_games))

    st.divider()
    st.caption("The five simulations")
    apps = [dict(r) for r in _all_apps()]
    cols = st.columns(len(apps))
    for col, app in zip(cols, apps):
        with col:
            st.markdown(f"**{app['name']}**")
            st.caption(app["app_key"].upper())

    if my_games:
        st.divider()
        st.caption("Recent games")
        for g in my_games[:5]:
            st.markdown(f"- {_STATUS.get(g['status'], g['status'])} **{g['title']}** "
                        f"· {g['app_name']} · code `{g['join_code']}`")
    else:
        st.divider()
        st.info("Start on the **Configurations** page to set a simulation's default "
                "values, then create a **Game** to get a join code for your class.")

    with st.expander("Change my password"):
        with st.form("self_pw"):
            pw = st.text_input("New password", type="password")
            pw2 = st.text_input("Confirm", type="password")
            if st.form_submit_button("Update password"):
                problem = auth.password_problem(pw, pw2)
                if problem:
                    st.error(problem)
                else:
                    db.set_password(u["id"], auth.hash_password(pw), must_change=0)
                    db.log_action(u["id"], "change_password", f"instructor:{u['id']}")
                    st.success("Password updated.")


def _all_apps():
    return db.list_apps()


# ----------------------------------------------------------------------------
# Router
# ----------------------------------------------------------------------------
def sidebar():
    u = current_user()
    with st.sidebar:
        st.markdown("### 🧃 Director")
        st.write(f"**{u['name']}**")
        st.caption("Grand Director" if u["role"] == "admin" else "Instructor")
        st.divider()
        nav = ["Dashboard", "Configurations", "Games"]
        if u["role"] == "admin":
            nav += ["Applications", "Administrator"]
        choice = st.radio("Go to", nav, label_visibility="collapsed")
        st.divider()
        if st.button("Sign out", use_container_width=True):
            sign_out()
        st.divider()
        if db.USE_DROPBOX:
            st.caption(f"🔒 {db.backend_name()} · persistent")
        else:
            st.caption("💾 Local SQLite · not persistent on cloud hosting")
    return choice


def screen_storage_error(err):
    st.title("🧃 Juicetification Director")
    st.error(
        "The encrypted-Dropbox persistence is configured but not usable yet, so "
        "the app can't reach its database."
    )
    st.markdown(
        "**How to fix:**\n\n"
        "1. Make sure `dropbox` and `cryptography` are installed (they're in "
        "`requirements.txt` by default) and redeploy.\n"
        "2. Check your secrets: `DB_ENCRYPTION_KEY` plus either "
        "`DROPBOX_REFRESH_TOKEN` + `DROPBOX_APP_KEY` + `DROPBOX_APP_SECRET`, or "
        "`DROPBOX_ACCESS_TOKEN`.\n"
        "3. To run locally without Dropbox, remove those secrets (note: the local "
        "file isn't persistent on cloud hosting)."
    )
    with st.expander("Technical detail"):
        st.code(err or "unknown error")


def main():
    # Fail clearly if persistence is half-configured or a package is missing.
    ok, err = db.storage_status()
    if not ok:
        screen_storage_error(err)
        return

    db.init_db()  # idempotent; safe to call on every run

    # Not signed in → first-run setup or login.
    if not current_user():
        if not db.any_admin_exists():
            screen_first_run()
        else:
            screen_login()
        return

    # Signed in but flagged for a forced password change.
    fresh = db.get_user(current_user()["id"])
    if not fresh or fresh["status"] != "active":
        sign_out()
        return
    if fresh["must_change_password"]:
        screen_force_password_change()
        return

    choice = sidebar()
    if choice == "Administrator" and is_admin():
        screen_admin_console()
    elif choice == "Applications" and is_admin():
        ui_apps.render_applications(current_user())
    elif choice == "Configurations":
        ui_configurations.render_configurations(current_user())
    elif choice == "Games":
        ui_games.render_games(current_user())
    else:
        screen_dashboard()


if __name__ == "__main__":
    main()
