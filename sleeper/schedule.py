"""NFL schedule from nflverse (Sleeper's API has no schedule endpoint): byes and opponents."""

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


@st.cache_data(ttl=3600, show_spinner=False)
def _regular_season(season: int) -> pd.DataFrame:
    """Regular-season games with Sleeper team abbreviations (empty if unavailable)."""
    try:
        games = pd.read_csv(NFLVERSE_GAMES, usecols=[
            "season", "game_type", "week", "away_team", "home_team", "away_score", "home_score"])
    except Exception:
        return pd.DataFrame()
    reg = games[(games.season == season) & (games.game_type == "REG")].copy()
    for side in ("away_team", "home_team"):
        reg[side] = reg[side].replace(TEAM_ALIASES)
    return reg


@st.cache_data(ttl=3600, show_spinner=False)
def team_games(season: int) -> dict[tuple[str, int], dict]:
    """(team, week) -> {"opponent": "vs DAL" / "@ SF", "result": "W 27-20" or ""}."""
    out = {}
    for g in _regular_season(season).itertuples():
        played = g.home_score == g.home_score and g.away_score == g.away_score  # not NaN
        for team, opp, at, own, other in (
            (g.home_team, g.away_team, "vs", g.home_score, g.away_score),
            (g.away_team, g.home_team, "@", g.away_score, g.home_score),
        ):
            result = ""
            if played:
                outcome = "W" if own > other else "L" if own < other else "T"
                result = f"{outcome} {own:.0f}-{other:.0f}"
            out[(team, int(g.week))] = {"opponent": f"{at} {opp}", "result": result}
    return out


@st.cache_data(ttl=86400, show_spinner=False)
def bye_weeks(season: int) -> dict[str, int]:
    """Map Sleeper team abbreviation -> regular-season bye week."""
    reg = _regular_season(season)
    if reg.empty:
        return FALLBACK_BYES.get(season, {})

    all_weeks = set(range(1, int(reg.week.max()) + 1))
    played: dict[str, set[int]] = {}
    for side in ("away_team", "home_team"):
        for team, week in zip(reg[side], reg.week):
            played.setdefault(team, set()).add(int(week))

    byes = {}
    for team, weeks in played.items():
        missing = all_weeks - weeks
        if missing:
            byes[team] = min(missing)
    return byes