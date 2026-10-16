"""NFL bye weeks, derived from the nflverse schedule (Sleeper's API has no schedule endpoint)."""

import pandas as pd
import streamlit as st

NFLVERSE_GAMES = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"

# nflverse abbreviation -> Sleeper abbreviation (only where they differ)
TEAM_ALIASES = {"LA": "LAR", "OAK": "LV", "SD": "LAC", "STL": "LAR"}

# Fallback if the download fails. Generated from nflverse for 2026.
FALLBACK_BYES = {
    2026: {
        "ARI": 14, "ATL": 11, "BAL": 13, "BUF": 7, "CAR": 5, "CHI": 10, "CIN": 6, "CLE": 11,
        "DAL": 14, "DEN": 10, "DET": 6, "GB": 11, "HOU": 8, "IND": 13, "JAX": 7, "KC": 5,
        "LAR": 11, "LAC": 7, "LV": 13, "MIA": 6, "MIN": 6, "NE": 11, "NO": 8, "NYG": 8,
        "NYJ": 13, "PHI": 10, "PIT": 9, "SEA": 11, "SF": 8, "TB": 10, "TEN": 9, "WAS": 7,
    }
}


@st.cache_data(ttl=86400, show_spinner=False)
def bye_weeks(season: int) -> dict[str, int]:
    """Map Sleeper team abbreviation -> regular-season bye week."""
    try:
        games = pd.read_csv(
            NFLVERSE_GAMES, usecols=["season", "game_type", "week", "away_team", "home_team"]
        )
    except Exception:
        return FALLBACK_BYES.get(season, {})

    reg = games[(games.season == season) & (games.game_type == "REG")]
    if reg.empty:
        return FALLBACK_BYES.get(season, {})

    all_weeks = set(range(1, int(reg.week.max()) + 1))
    played: dict[str, set[int]] = {}
    for side in ("away_team", "home_team"):
        for team, week in zip(reg[side], reg.week):
            played.setdefault(TEAM_ALIASES.get(team, team), set()).add(int(week))

    byes = {}
    for team, weeks in played.items():
        missing = all_weeks - weeks
        if missing:
            byes[team] = min(missing)
    return byes