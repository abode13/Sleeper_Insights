"""Thin client for the public Sleeper API (read-only, no auth).

Docs: https://docs.sleeper.com/
"""

from concurrent.futures import ThreadPoolExecutor

import requests
import streamlit as st

BASE = "https://api.sleeper.app/v1"
_session = requests.Session()


def _get(path: str):
    resp = _session.get(f"{BASE}{path}", timeout=30)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=900, show_spinner=False)
def nfl_state() -> dict:
    return _get("/state/nfl")


@st.cache_data(ttl=900, show_spinner=False)
def league(league_id: str) -> dict:
    return _get(f"/league/{league_id}")


@st.cache_data(ttl=900, show_spinner=False)
def users(league_id: str) -> list[dict]:
    return _get(f"/league/{league_id}/users")


@st.cache_data(ttl=900, show_spinner=False)
def rosters(league_id: str) -> list[dict]:
    return _get(f"/league/{league_id}/rosters")


@st.cache_data(ttl=900, show_spinner=False)
def matchups_many(league_id: str, weeks: tuple[int, ...]) -> dict[int, list[dict]]:
    """Fetch several weeks in parallel (plain HTTP in threads; cached as a whole)."""
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = pool.map(lambda w: _get(f"/league/{league_id}/matchups/{w}") or [], weeks)
        return dict(zip(weeks, results))


@st.cache_data(ttl=3600, show_spinner="Loading NFL player stats…")
def weekly_stats(season: int, weeks: tuple[int, ...],
                 stat_keys: tuple[str, ...]) -> dict[int, dict[str, dict]]:
    """Every NFL player's stats per week: week -> player_id -> {stat: value}.

    Undocumented endpoint (it's what Sleeper's own app uses), so callers must handle
    failures. Slimmed to the stats the league scores plus games played ("gp").
    """
    keep = set(stat_keys) | {"gp"}

    def fetch(week):
        raw = _get(f"/stats/nfl/regular/{season}/{week}") or {}
        return {pid: {k: v for k, v in s.items() if k in keep}
                for pid, s in raw.items() if isinstance(s, dict)}

    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(zip(weeks, pool.map(fetch, weeks)))


@st.cache_data(ttl=86400, show_spinner="Loading NFL player database…")
def players() -> dict[str, dict]:
    """All NFL players, slimmed down to the fields we use.

    The full payload is ~5 MB; Sleeper asks to fetch it at most once per day.
    """
    raw = _get("/players/nfl")
    slim = {}
    for pid, p in raw.items():
        pos = p.get("position")
        name = p.get("full_name") or " ".join(
            x for x in (p.get("first_name"), p.get("last_name")) if x
        )
        slim[pid] = {
            "name": name or pid,
            "pos": pos or "?",
            "team": p.get("team"),
            "fantasy_positions": p.get("fantasy_positions") or ([pos] if pos else []),
            "injury_status": p.get("injury_status"),
        }
    return slim