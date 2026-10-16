"""Password-unlocked private features (projections & rankings only the owner sees).

The password lives in Streamlit secrets as PRIVATE_PASSWORD. Unlocking is per browser
session; other visitors never see the private columns or data.
"""

import hmac

import streamlit as st

_STATE_KEY = "private_unlocked"


def _secret(name: str) -> str | None:
    try:
        value = st.secrets.get(name)
    except Exception:  # no secrets.toml
        return None
    return str(value) if value else None


def enabled() -> bool:
    return _secret("PRIVATE_PASSWORD") is not None


def is_unlocked() -> bool:
    return enabled() and st.session_state.get(_STATE_KEY, False)


def fantasypros_key() -> str | None:
    return _secret("FANTASYPROS_API_KEY") if is_unlocked() else None


def unlock_widget() -> None:
    """Small sidebar control to unlock / lock the private features."""
    if not enabled():
        return
    if is_unlocked():
        if st.button("🔓 Lock private view", width="stretch"):
            st.session_state[_STATE_KEY] = False
            st.rerun()
        return
    with st.expander("🔒 Private"):
        with st.form("private_unlock", border=False):
            pw = st.text_input("Password", type="password", label_visibility="collapsed",
                               placeholder="Password")
            if st.form_submit_button("Unlock", width="stretch"):
                if hmac.compare_digest(pw.encode(), _secret("PRIVATE_PASSWORD").encode()):
                    st.session_state[_STATE_KEY] = True
                    st.rerun()
                st.error("Wrong password")
