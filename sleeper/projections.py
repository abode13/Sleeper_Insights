"""Private projections & rankings: Sleeper projections (league scoring) and FantasyPros ECR.

Only used when the private view is unlocked (see sleeper/private.py).
"""

import re
import unicodedata

import pandas as pd

from sleeper import api
from sleeper.model import LeagueData

FP_POSITIONS = {"QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "K": "K", "DST": "DEF"}
FP_TEAM_ALIASES = {"JAC": "JAX", "LA": "LAR", "WSH": "WAS"}


def projection_weeks(data: LeagueData) -> list[int]:
    """The week shown as 'this week' first, then the rest of the regular season."""
    first = data.current_week
    if first > 18:
        return []
    last = max(first, data.last_regular_week)
    return list(range(first, last + 1))


def _league_points(s: dict, scoring: dict) -> float:
    s = dict(s)
    # Projections lack a few kicker stats the league scores; derive them
    if "fgmiss" not in s and "fga" in s:
        s["fgmiss"] = max(float(s.get("fga") or 0) - float(s.get("fgm") or 0), 0.0)
    if "fgm_yds_over_30" not in s and "fgm_yds" in s:
        s["fgm_yds_over_30"] = max(float(s["fgm_yds"]) - 30 * float(s.get("fgm") or 0), 0.0)
    return sum(float(s.get(k) or 0) * v for k, v in scoring.items())


def sleeper_projections(data: LeagueData) -> pd.DataFrame:
    """player_id, proj_week (this week, league scoring), proj_ros (average per projected game
    from this week to the end of the regular season; byes don't count as games).
    Empty if Sleeper's projections are unavailable."""
    weeks = projection_weeks(data)
    cols = ["player_id", "proj_week", "proj_ros"]
    if not weeks or not data.scoring:
        return pd.DataFrame(columns=cols)
    try:
        weekly = api.projections(data.season, tuple(weeks), tuple(sorted(data.scoring)))
    except Exception:
        return pd.DataFrame(columns=cols)
    rows = [(week, pid, _league_points(s, data.scoring))
            for week, players in weekly.items() for pid, s in players.items()]
    df = pd.DataFrame(rows, columns=["week", "player_id", "pts"])
    if df.empty:
        return pd.DataFrame(columns=cols)
    this_week = df[df.week == weeks[0]].set_index("player_id").pts
    # Only weeks with a projected game are in the data (projections are filtered on gp)
    ros = df[df.week <= data.last_regular_week].groupby("player_id").pts.mean()
    out = pd.DataFrame({"proj_week": this_week, "proj_ros": ros}).rename_axis("player_id")
    return out.reset_index()


# ---------------------------------------------------------------- FantasyPros

def _norm(name: str) -> str:
    name = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    name = re.sub(r"[^a-z ]", "", name.lower().replace("-", " "))
    return re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", name).strip().replace("  ", " ")


def _first(d: dict, *keys, default=None):
    for k in keys:
        if d.get(k) not in (None, ""):
            return d[k]
    return default


def _players(payload: dict) -> list[dict]:
    if isinstance(payload, dict):
        for key in ("players", "data", "rankings"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return payload if isinstance(payload, list) else []


def fantasypros(data: LeagueData, api_key: str) -> tuple[pd.DataFrame, list[str]]:
    """FantasyPros consensus ranks (this week + rest of season) and weekly projection.

    Columns: player_id, fp_ecr, fp_pos_rank, fp_ros_ecr, fp_ros_pos_rank, fp_proj
    (half PPR). Returns (frame, names that couldn't be matched to Sleeper players).
    """
    weeks = projection_weeks(data)
    cols = ["player_id", "fp_ecr", "fp_pos_rank", "fp_ros_ecr", "fp_ros_pos_rank", "fp_proj"]
    if not weeks or not api_key:
        return pd.DataFrame(columns=cols), []
    week = weeks[0]

    # Sleeper lookup: (normalized name, position) -> [(player_id, team)]
    index: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for pid, p in data.players.items():
        if p["pos"] in FP_POSITIONS.values() and p["pos"] != "DEF":
            index.setdefault((_norm(p["name"]), p["pos"]), []).append((pid, p.get("team")))

    def match(row: dict, sleeper_pos: str) -> str | None:
        team = str(_first(row, "player_team_id", "team_id", "team", default="")).upper()
        team = FP_TEAM_ALIASES.get(team, team)
        if sleeper_pos == "DEF":
            return team if team in data.players else None
        candidates = index.get((_norm(_first(row, "player_name", "name", default="")),
                                sleeper_pos), [])
        if len(candidates) > 1:
            candidates = [c for c in candidates if c[1] == team] or candidates
        return candidates[0][0] if candidates else None

    rows, unmatched = {}, []
    rank_types = (("weekly", (("type", "weekly"), ("week", week)), "fp"),
                  ("ros", (("type", "ros"),), "fp_ros"))

    def rankings(fp_pos, params):
        return _players(api.fantasypros("consensus-rankings", data.season, (
            ("position", fp_pos), ("scoring", "HALF"), *params), api_key))

    # Position ranks (e.g. WR3) from each position's list. Note: the free public API only
    # returns the top 10 players of every list.
    for fp_pos, sleeper_pos in FP_POSITIONS.items():
        for kind, params, prefix in rank_types:
            for r in rankings(fp_pos, params):
                pid = match(r, sleeper_pos)
                if pid is None:
                    if kind == "weekly":
                        unmatched.append(str(_first(r, "player_name", "name", default="?")))
                    continue
                rows.setdefault(pid, {"player_id": pid})[f"{prefix}_pos_rank"] = _first(
                    r, "pos_rank", "position_rank")
        projs = api.fantasypros("projections", data.season, (
            ("position", fp_pos), ("week", week), ("scoring", "HALF")), api_key)
        for r in _players(projs):
            pid = match(r, sleeper_pos)
            if pid is None:
                continue
            stats = r.get("stats") if isinstance(r.get("stats"), dict) else {}
            # points_half matches the HALF scoring requested; plain "points" is standard
            pts = _first(stats, "points_half", "points") or _first(r, "fpts", "points")
            rows.setdefault(pid, {"player_id": pid})["fp_proj"] = pts

    # Overall rank from the overall list: "OP" includes QBs (superflex), "ALL" is FLEX-style
    overall = "OP" if "SUPER_FLEX" in data.roster_positions else "ALL"
    for kind, params, prefix in rank_types:
        for r in rankings(overall, params):
            sleeper_pos = FP_POSITIONS.get(str(r.get("player_position_id")), None)
            pid = match(r, sleeper_pos) if sleeper_pos else None
            if pid is not None:
                rows.setdefault(pid, {"player_id": pid})[f"{prefix}_ecr"] = _first(
                    r, "rank_ecr", "ecr", "rank")

    df = pd.DataFrame(list(rows.values()), columns=cols)
    for c in ("fp_ecr", "fp_ros_ecr", "fp_proj"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df, unmatched
