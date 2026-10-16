import os

import streamlit as st

import sleeper.theme  # noqa: F401  (registers the plotly template)
from sleeper import api
from sleeper.model import load_league

st.set_page_config(page_title="Sleeper League Dashboard", page_icon="🏈", layout="wide")


def configured_league_id() -> str | None:
    try:
        if "LEAGUE_ID" in st.secrets:
            return str(st.secrets["LEAGUE_ID"])
    except Exception:  # no secrets.toml
        pass
    return os.environ.get("LEAGUE_ID") or st.query_params.get("league")


league_id = configured_league_id()
if not league_id:
    st.title("Sleeper League Dashboard")
    st.info("No league configured. Set `LEAGUE_ID` in `.streamlit/secrets.toml` "
            "or enter it below (it's the number in your sleeper.com league URL).")
    entered = st.text_input("League ID")
    if entered:
        st.query_params["league"] = entered.strip()
        st.rerun()
    st.stop()

try:
    data = load_league(league_id)
except Exception as exc:
    st.error(f"Could not load league `{league_id}`: {exc}")
    st.stop()

st.session_state["data"] = data

with st.sidebar:
    st.markdown(f"### {data.name}")
    if data.current_week > data.last_regular_week:
        st.caption(f"{data.season} season · regular season complete")
    else:
        st.caption(f"{data.season} season · week {data.current_week} in progress")
    if st.button("Refresh data", width="stretch"):
        # Keep the 24h player database cache; Sleeper asks not to refetch it often
        for fn in (load_league, api.nfl_state, api.league, api.users, api.rosters,
                   api.matchups_many):
            fn.clear()
        st.rerun()

pages = [
    st.Page("pages/standings.py", title="Standings", icon="🏆", default=True),
    st.Page("pages/weekly.py", title="Weekly", icon="📅"),
    st.Page("pages/teams.py", title="Teams", icon="👥"),
    st.Page("pages/players.py", title="Players", icon="🏃"),
    st.Page("pages/bye_luck.py", title="Bye luck", icon="🍀"),
]
st.navigation(pages).run()