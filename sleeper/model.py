"""Turn raw Sleeper JSON into tidy pandas DataFrames."""

from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

from sleeper import api, schedule, statcols

AVATAR_URL = "https://sleepercdn.com/avatars/thumbs/{}"


@dataclass
class LeagueData:
    league_id: str
    name: str
    season: int
    current_week: int  # NFL week in progress (weeks before it are final)
    last_regular_week: int
    median_game: bool  # league plays an extra game vs. the weekly median
    playoff_teams: int
    playoff_round_type: int  # 0: 1 week per round, 1: 2-week final, 2: 2 weeks per round
    roster_positions: list[str]
    teams: pd.DataFrame  # one row per roster
    team_weeks: pd.DataFrame  # one row per team per week that has scores
    player_weeks: pd.DataFrame  # one row per rostered player per week that has scores
    schedule: pd.DataFrame  # regular season pairings incl. future weeks
    week_rosters: dict = field(default_factory=dict)  # (week, roster_id) -> [player_id]
    current_rosters: dict = field(default_factory=dict)  # roster_id -> [player_id]
    players: dict = field(default_factory=dict)  # player_id -> slim player info
    byes: dict = field(default_factory=dict)  # NFL team -> bye week
    divisions: dict = field(default_factory=dict)  # division number -> {"name", "avatar"}
    # Every NFL player's completed weeks scored with this league's settings:
    # week, player_id, points, played. Empty if Sleeper's stats endpoint failed.
    player_stats: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def has_nfl_stats(self) -> bool:
        return not self.player_stats.empty

    def team_name(self, roster_id) -> str:
        return self.names.get(roster_id, f"Team {roster_id}")

    @property
    def names(self) -> dict:
        return dict(zip(self.teams.roster_id, self.teams.team))

    def player(self, pid: str) -> dict:
        return self.players.get(pid) or {
            "name": pid, "pos": "?", "team": None, "fantasy_positions": [], "injury_status": None
        }


def _current_week(state: dict, season: int, last_regular_week: int) -> int:
    """First week that is not final yet."""
    league_season = int(state.get("league_season") or state["season"])
    if season < league_season or state.get("season_type") == "post":
        return 99  # season is over
    if state.get("season_type") == "pre" or season > league_season:
        return 1
    return int(state.get("week") or 1)


def _teams(users: list[dict], rosters: list[dict]) -> pd.DataFrame:
    by_id = {u["user_id"]: u for u in users}
    rows = []
    for r in rosters:
        u = by_id.get(r.get("owner_id")) or {}
        meta = u.get("metadata") or {}
        s = r.get("settings") or {}
        avatar = meta.get("avatar") or (AVATAR_URL.format(u["avatar"]) if u.get("avatar") else None)
        rows.append({
            "roster_id": r["roster_id"],
            "team": (meta.get("team_name") or u.get("display_name")
                     or f"Team {r['roster_id']}").strip(),
            "owner": u.get("display_name") or "—",
            "avatar": avatar,
            "division": s.get("division"),
            # Sleeper's own numbers, kept for cross-checking our calculations
            "sleeper_wins": s.get("wins", 0),
            "sleeper_losses": s.get("losses", 0),
            "sleeper_ties": s.get("ties", 0),
            "sleeper_fpts": s.get("fpts", 0) + s.get("fpts_decimal", 0) / 100,
        })
    return pd.DataFrame(rows).sort_values("roster_id").reset_index(drop=True)


def _player_stats(season: int, current_week: int, scoring_settings: dict) -> pd.DataFrame:
    """Score every NFL player's completed weeks with the league's own scoring rules.

    Sleeper's matchups only report points for rostered players and can't tell a missed
    game from a 0-point game; the weekly stats endpoint has both. Returns an empty frame
    if that (undocumented) endpoint fails, and callers fall back to matchup points.
    """
    scoring = {k: float(v) for k, v in scoring_settings.items() if v}
    weeks = tuple(range(1, min(current_week, 19)))
    columns = ["week", "player_id", "points", "played"] + statcols.ALL
    if not scoring or not weeks:
        return pd.DataFrame(columns=columns)
    try:
        weekly = api.weekly_stats(season, weeks, tuple(sorted(set(scoring) | set(statcols.ALL))))
    except Exception:
        return pd.DataFrame(columns=columns)
    rows = [
        (week, pid, round(sum(float(s.get(k) or 0) * v for k, v in scoring.items()), 2),
         float(s.get("gp") or 0) > 0, *(float(s.get(k) or 0) for k in statcols.ALL))
        for week, stats in weekly.items() for pid, s in stats.items()
    ]
    df = pd.DataFrame(rows, columns=columns)
    df[statcols.ALL] = df[statcols.ALL].astype("float32")  # ~40k rows by season's end
    return df


def _divisions(lg: dict) -> dict[int, dict]:
    meta = lg.get("metadata") or {}
    n = int((lg.get("settings") or {}).get("divisions") or 0)
    return {d: {"name": meta.get(f"division_{d}") or f"Division {d}",
                "avatar": meta.get(f"division_{d}_avatar")}
            for d in range(1, n + 1)}


def _points(m: dict) -> float:
    custom = m.get("custom_points")
    return float(custom if custom is not None else (m.get("points") or 0))


@st.cache_data(ttl=900, show_spinner="Loading league from Sleeper…")
def load_league(league_id: str) -> LeagueData:
    lg = api.league(league_id)
    if not lg:
        raise ValueError(f"League {league_id} not found")
    settings = lg.get("settings") or {}
    season = int(lg["season"])
    last_regular = int(settings.get("playoff_week_start") or 15) - 1
    current_week = _current_week(api.nfl_state(), season, last_regular)

    users, rosters = api.users(league_id), api.rosters(league_id)
    players = api.players()
    teams = _teams(users, rosters)

    max_week = max(last_regular, min(current_week, 18))
    weekly = api.matchups_many(league_id, tuple(range(1, max_week + 1)))

    tw_rows, pw_rows, sched_rows, week_rosters = [], [], [], {}
    for week, entries in weekly.items():
        has_scores = week <= current_week and any(_points(m) > 0 for m in entries)
        opp = {}
        for mid in {m.get("matchup_id") for m in entries if m.get("matchup_id") is not None}:
            pair = [m["roster_id"] for m in entries if m.get("matchup_id") == mid]
            if len(pair) == 2:
                opp[pair[0]], opp[pair[1]] = pair[1], pair[0]
        pts = {m["roster_id"]: _points(m) for m in entries}

        for m in entries:
            rid = m["roster_id"]
            if week <= last_regular:
                sched_rows.append({"week": week, "roster_id": rid, "opp_roster_id": opp.get(rid)})
            if week <= current_week and m.get("players"):
                week_rosters[(week, rid)] = list(m["players"])
            if not has_scores:
                continue
            o = opp.get(rid)
            tw_rows.append({
                "week": week,
                "roster_id": rid,
                "matchup_id": m.get("matchup_id"),
                "opp_roster_id": o,
                "points": pts[rid],
                "opp_points": pts.get(o) if o is not None else None,
                "final": week < current_week,
                "regular": week <= last_regular,
            })
            starters = set(m.get("starters") or [])
            for pid, p in (m.get("players_points") or {}).items():
                info = players.get(pid) or {}
                pw_rows.append({
                    "week": week,
                    "roster_id": rid,
                    "player_id": pid,
                    "name": info.get("name", pid),
                    "pos": info.get("pos", "?"),
                    "nfl_team": info.get("team"),
                    "points": float(p or 0),
                    "is_starter": pid in starters,
                })

    team_weeks = pd.DataFrame(tw_rows, columns=[
        "week", "roster_id", "matchup_id", "opp_roster_id", "points", "opp_points", "final", "regular"])
    if not team_weeks.empty:
        team_weeks["week_median"] = team_weeks.groupby("week").points.transform("median")
        team_weeks["beat_median"] = team_weeks.points > team_weeks.week_median
        diff = team_weeks.points - team_weeks.opp_points
        team_weeks["result"] = None
        has_opp = team_weeks.opp_points.notna() & team_weeks.final
        team_weeks.loc[has_opp & (diff > 0), "result"] = "W"
        team_weeks.loc[has_opp & (diff < 0), "result"] = "L"
        team_weeks.loc[has_opp & (diff == 0), "result"] = "T"
        team_weeks["team"] = team_weeks.roster_id.map(dict(zip(teams.roster_id, teams.team)))

    return LeagueData(
        league_id=league_id,
        name=lg.get("name", "League"),
        season=season,
        current_week=current_week,
        last_regular_week=last_regular,
        median_game=bool(settings.get("league_average_match")),
        playoff_teams=int(settings.get("playoff_teams") or 6),
        playoff_round_type=int(settings.get("playoff_round_type") or 0),
        roster_positions=list(lg.get("roster_positions") or []),
        teams=teams,
        team_weeks=team_weeks,
        player_weeks=pd.DataFrame(pw_rows, columns=[
            "week", "roster_id", "player_id", "name", "pos", "nfl_team", "points", "is_starter"]),
        schedule=pd.DataFrame(sched_rows, columns=["week", "roster_id", "opp_roster_id"]),
        week_rosters=week_rosters,
        current_rosters={r["roster_id"]: list(r.get("players") or []) for r in rosters},
        players=players,
        byes=schedule.bye_weeks(season),
        divisions=_divisions(lg),
        player_stats=_player_stats(season, current_week, lg.get("scoring_settings") or {}),
    )