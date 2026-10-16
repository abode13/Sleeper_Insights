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
    return os.environ.get("LEAGUE_ID")


# A league chosen in the URL or the input box is remembered for the session, because
# switching pages drops the URL's query parameters
league_id = configured_league_id()
if not league_id:
    league_id = st.query_params.get("league") or st.session_state.get("league_id")
    if league_id:
        st.session_state["league_id"] = league_id
        st.query_params["league"] = league_id  # keep it in the URL so it can be shared
if not league_id:
    st.title("Sleeper League Dashboard")
    st.info("No league configured. Set `LEAGUE_ID` in `.streamlit/secrets.toml` "
            "or enter it below (it's the number in your sleeper.com league URL).")
    entered = st.text_input("League ID")
    if entered:
        st.session_state["league_id"] = entered.strip()
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
    if not data.has_nfl_stats:
        st.caption("⚠️ NFL player stats unavailable — averages use league matchup points.")
    if st.button("Refresh data", width="stretch"):
        # Keep the 24h player database cache; Sleeper asks not to refetch it often
        for fn in (load_league, api.nfl_state, api.league, api.users, api.rosters,
                   api.matchups_many, api.weekly_stats):
            fn.clear()
        st.rerun()

pages = [
    st.Page("views/standings.py", title="Standings", icon="🏆", default=True),
    st.Page("views/weekly.py", title="Weekly", icon="📅"),
    st.Page("views/teams.py", title="Teams", icon="👥"),
    st.Page("views/players.py", title="Players", icon="🏃"),
    st.Page("views/bye_luck.py", title="Bye luck", icon="🍀"),
]
st.navigation(pages).run()