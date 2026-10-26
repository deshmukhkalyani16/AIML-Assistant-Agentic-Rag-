SSO = r"""PROVIDER_LABELS = {
    "google": "Continue with Google",
    "microsoft": "Continue with Microsoft",
    "auth0": "Continue with Facebook, GitHub and more",
    "okta": "Continue with Okta",
}


def sso_user():
    try:
        u = st.user
        if getattr(u, "is_logged_in", False):
            return u
    except Exception:
        pass
    return None


def sso_providers():
    try:
        cfg = st.secrets["auth"]
    except Exception:
        return []
    out = []
    for k in cfg:
        try:
            if hasattr(cfg[k], "keys"):
                out.append((k, PROVIDER_LABELS.get(k, "Continue with " + str(k).title())))
        except Exception:
            pass
    if not out and "client_id" in cfg:
        out.append((None, "Continue with single sign-on"))
    return out


"""

SOCIAL = r"""        providers = sso_providers()
        st.divider()
        if providers:
            st.markdown("**Or continue with**")
            for prov, label in providers:
                st.button(label, key="sso_" + str(prov), on_click=st.login, args=[prov])
        else:
            st.caption("Social login (Google, Facebook, ...) is not set up yet.")
"""

GATE = r"""if not st.session_state.get("user"):
    su = sso_user()
    ident = str(getattr(su, "email", None) or getattr(su, "sub", None) or "") if su is not None else ""
    if ident:
        st.session_state["user"] = "sso_" + hashlib.sha256(ident.encode("utf-8")).hexdigest()[:16]
        st.session_state["display"] = str(getattr(su, "name", None) or getattr(su, "email", None) or "Signed-in user")
    else:
        login_page()
        st.stop()
"""

EDITS = [
    ("social helpers", "def cb_logout():", SSO + "def cb_logout():"),
    ("logout", '              "fails", "locked_until"]:\n        st.session_state.pop(k, None)\n',
     '              "fails", "locked_until", "display"]:\n        st.session_state.pop(k, None)\n'
     '    if sso_user() is not None:\n        st.logout()\n'),
    ("reserved names", '    if username == "guest":\n        return "That username is reserved."\n',
     '    if username == "guest" or username.startswith("sso_"):\n        return "That username is reserved."\n'),
    ("social buttons", '        st.divider()\n        if st.button("Continue as guest (chats are not saved)"):',
     SOCIAL + '        st.divider()\n        if st.button("Continue as guest (chats are not saved)"):'),
    ("login gate", 'if not st.session_state.get("user"):\n    login_page()\n    st.stop()\n', GATE),
    ("sidebar name", '        st.caption("Signed in as " + st.session_state["user"])',
     '        st.caption("Signed in as " + str(st.session_state.get("display") or st.session_state["user"]))'),
]

s = open("app.py", encoding="utf-8").read()
if "def sso_user" in s:
    print("app.py: social login already added")
else:
    for name, old, new in EDITS:
        if old in s:
            s = s.replace(old, new, 1)
            print("applied:", name)
        else:
            print("NOT FOUND:", name)
    open("app.py", "w", encoding="utf-8").write(s)
