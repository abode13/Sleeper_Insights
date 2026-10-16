"""League statistics built on top of LeagueData."""

import pandas as pd

from sleeper import statcols
from sleeper.model import LeagueData

# Lineup slot -> positions that may fill it
SLOT_ELIGIBILITY = {
    "FLEX": {"RB", "WR", "TE"},
    "WRRB_FLEX": {"WR", "RB"},
    "REC_FLEX": {"WR", "TE"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
    "IDP_FLEX": {"DL", "LB", "DB", "DE", "DT", "CB", "S"},
    "DL": {"DL", "DE", "DT"},
    "DB": {"DB", "CB", "S"},
}
NON_STARTING_SLOTS = {"BN", "IR", "TAXI"}


# ---------------------------------------------------------------- standings

def standings(data: LeagueData) -> pd.DataFrame:
    tw = data.team_weeks
    tw = tw[tw.final & tw.regular]
    division_of = dict(zip(data.teams.roster_id, data.teams.division))
    rows = []
    for t in data.teams.itertuples():
        g = tw[tw.roster_id == t.roster_id]
        w, l, ties = (g.result == "W").sum(), (g.result == "L").sum(), (g.result == "T").sum()
        mw = int(g.beat_median.sum())
        ml = len(g) - mw
        in_div = g[g.opp_roster_id.map(division_of) == t.division] if t.division else g.iloc[:0]
        rows.append({
            "roster_id": t.roster_id,
            "avatar": t.avatar,
            "team": t.team,
            "owner": t.owner,
            "division": t.division,
            "W": int(w), "L": int(l), "T": int(ties),
            "Div W": int((in_div.result == "W").sum()), "Div L": int((in_div.result == "L").sum()),
            "Med W": mw, "Med L": ml,
            "PF": g.points.sum(),
            "PA": g.opp_points.sum(),
            "Avg PF": g.points.mean() if len(g) else 0.0,
        })
    df = pd.DataFrame(rows)
    if data.median_game:
        df["Tot W"], df["Tot L"] = df.W + df["Med W"], df.L + df["Med L"]
    else:
        df["Tot W"], df["Tot L"] = df.W, df.L
    df = df.merge(all_play(data), on="roster_id", how="left")
    df["Luck"] = df.W - df["Exp W"]
    # Sleeper's tiebreakers: record, then points for, then points against (higher wins)
    df["_record"] = df["Tot W"] + 0.5 * df["T"]
    df = df.sort_values(["_record", "PF", "PA"], ascending=False).drop(columns="_record")
    df = df.reset_index(drop=True)
    df.insert(0, "Rank", range(1, len(df) + 1))
    return df


def playoff_picture(data: LeagueData, table: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    """Seeds if the season ended today, following Sleeper's rules.

    With divisions, every division leader qualifies and takes the top seeds; the remaining
    spots go to the best other teams. `table` must be sorted like `standings()`.

    Returns (seeded table incl. non-qualifiers, first-round pairings as (seed, seed|None)).
    """
    n = min(data.playoff_teams, len(table))
    df = table.copy()
    if data.divisions and df.division.notna().any():
        leaders = df.groupby("division", sort=False).head(1)
        leaders = leaders.head(n)  # more divisions than spots: best leaders only
        others = df.drop(leaders.index)
        seeded = pd.concat([leaders, others.head(n - len(leaders))])
        df["Status"] = "Out"
        df.loc[others.head(n - len(leaders)).index, "Status"] = "Wildcard"
        df.loc[leaders.index, "Status"] = "Division leader"
    else:
        seeded = df.head(n)
        df["Status"] = "Out"
        df.loc[seeded.index, "Status"] = "In"
    df["Seed"] = float("nan")
    df.loc[seeded.index, "Seed"] = range(1, len(seeded) + 1)

    # Bracket: pad to the next power of two; top seeds fill the gaps with byes
    size = 1
    while size < n:
        size *= 2
    byes = size - n
    df.loc[df.Seed.notna() & (df.Seed <= byes), "Status"] += " · bye"
    pairs = [(s, None) for s in range(1, byes + 1)]
    rest = list(range(byes + 1, n + 1))
    while len(rest) >= 2:
        pairs.append((rest.pop(0), rest.pop()))

    # Games behind the last playoff spot (for teams outside)
    if n:
        cut = df.loc[df.Seed == n].iloc[0]
        cut_w, cut_l = cut["Tot W"], cut["Tot L"]
        df["GB"] = ((cut_w - df["Tot W"]) + (df["Tot L"] - cut_l)) / 2
        df.loc[df.Seed.notna(), "GB"] = float("nan")
    seeded_first = pd.concat([df[df.Seed.notna()].sort_values("Seed"), df[df.Seed.isna()]])
    return seeded_first.reset_index(drop=True), pairs


def all_play(data: LeagueData) -> pd.DataFrame:
    """Record if every team played every other team each week; expected H2H wins."""
    tw = data.team_weeks
    tw = tw[tw.final & tw.regular]
    rows = []
    for week, g in tw.groupby("week"):
        n = len(g) - 1
        for r in g.itertuples():
            beat = (g.points < r.points).sum() + 0.5 * ((g.points == r.points).sum() - 1)
            rows.append({"roster_id": r.roster_id, "ap_w": beat, "ap_l": n - beat,
                         "exp_w": beat / n if n else 0})
    if not rows:
        return pd.DataFrame(columns=["roster_id", "AP W", "AP L", "AP %", "Exp W"])
    ap = pd.DataFrame(rows).groupby("roster_id").sum().reset_index()
    ap["AP %"] = ap.ap_w / (ap.ap_w + ap.ap_l)
    return ap.rename(columns={"ap_w": "AP W", "ap_l": "AP L", "exp_w": "Exp W"})


# ---------------------------------------------------------------- lineups

def starting_slots(data: LeagueData) -> list[str]:
    slots = [s for s in data.roster_positions if s not in NON_STARTING_SLOTS]
    # Fill the most restrictive slots first so greedy picks stay close to optimal
    return sorted(slots, key=lambda s: len(SLOT_ELIGIBILITY.get(s, {s})))


def optimal_lineup(candidates: list[tuple[str, list[str], float]], slots: list[str]):
    """Greedy best lineup. candidates: (player_id, eligible positions, value).

    Returns (total, chosen player ids).
    """
    pool = sorted(candidates, key=lambda c: c[2], reverse=True)
    used, total = set(), 0.0
    for slot in slots:
        allowed = SLOT_ELIGIBILITY.get(slot, {slot})
        for pid, positions, value in pool:
            if pid not in used and allowed.intersection(positions):
                used.add(pid)
                total += value
                break
    return total, used


def lineup_efficiency(data: LeagueData) -> pd.DataFrame:
    """Actual vs. optimal points per team-week (based on that week's actual player points)."""
    slots = starting_slots(data)
    rows = []
    for (week, rid), g in data.player_weeks.groupby(["week", "roster_id"]):
        cands = [(p, data.player(p)["fantasy_positions"], pts)
                 for p, pts in zip(g.player_id, g.points)]
        best, _ = optimal_lineup(cands, slots)
        actual = g.loc[g.is_starter, "points"].sum()
        rows.append({
            "week": week, "roster_id": rid, "actual": actual, "optimal": best,
            "left_on_bench": best - actual, "bench_points": g.loc[~g.is_starter, "points"].sum(),
        })
    df = pd.DataFrame(rows, columns=["week", "roster_id", "actual", "optimal",
                                     "left_on_bench", "bench_points"])
    df["efficiency"] = df.actual / df.optimal.where(df.optimal > 0)
    return df


# ---------------------------------------------------------------- players

def player_values(data: LeagueData) -> pd.Series:
    """Average points per game this season, in league scoring.

    Uses every NFL game the player actually played (Sleeper's weekly stats). Fallback
    when those stats are unavailable: weeks on a league roster, with 0-point weeks
    treated as missed games.
    """
    if data.has_nfl_stats:
        ps = data.player_stats
        ps = ps[ps.played & (ps.week < data.current_week)]
        return ps.groupby("player_id").points.mean()
    pw = data.player_weeks
    pw = pw[(pw.week < data.current_week) & (pw.points != 0)]
    return pw.groupby("player_id").points.mean()


def games_played(data: LeagueData) -> pd.Series:
    """NFL games played per player this season (empty without Sleeper's weekly stats)."""
    ps = data.player_stats
    if not data.has_nfl_stats:
        return pd.Series(dtype=int)
    return ps[ps.played & (ps.week < data.current_week)].groupby("player_id").size()


def player_season_stats(data: LeagueData, keys: list[str], per_game: bool) -> pd.DataFrame:
    """NFL stat lines per player over the completed weeks (games actually played)."""
    ps = data.player_stats
    ps = ps[ps.played & (ps.week < data.current_week)]
    g = ps.groupby("player_id")
    out = pd.DataFrame(index=g.size().index)
    games = g.size()
    for k in keys:
        if k in statcols.SEASON_MAX:
            out[k] = g[k].max()
        elif per_game or k in statcols.ALWAYS_PER_GAME:
            out[k] = g[k].sum() / games
        else:
            out[k] = g[k].sum()
    return out


def player_weekly_detail(data: LeagueData, pid: str) -> pd.DataFrame:
    """One player's weeks: league points, whether he played, fantasy team, NFL stats."""
    pos = data.player(pid)["pos"]
    keys = statcols.BY_POSITION.get(pos, statcols.MIXED)
    weeks = range(1, data.current_week if data.current_week < 99 else 19)
    df = pd.DataFrame({"week": list(weeks)})
    pw = data.player_weeks[data.player_weeks.player_id == pid].set_index("week")
    df["fantasy_team"] = df.week.map(pw.roster_id).map(data.names)
    df["started"] = df.week.map(pw.is_starter)
    if data.has_nfl_stats:
        ps = data.player_stats[data.player_stats.player_id == pid].set_index("week")
        # Plus every other stat this league scores that the player actually recorded
        extra = [k for k in data.scoring if k not in keys and k in ps and ps[k].any()]
        keys = keys + sorted(extra, key=lambda k: (k not in statcols.SCORED_LABELS,
                                                   list(statcols.SCORED_LABELS).index(k)
                                                   if k in statcols.SCORED_LABELS else 0, k))
        df["played"] = df.week.map(ps.played).fillna(False).astype(bool)
        df["points"] = df.week.map(ps.points)
        for k in keys:
            df[k] = df.week.map(ps[k])
        df.loc[~df.played, ["points"] + keys] = float("nan")
    else:
        df["played"] = df.week.map(pw.points).fillna(0) != 0
        df["points"] = df.week.map(pw.points)
    bye = data.byes.get(data.player(pid)["team"])
    df["note"] = ""
    df.loc[df.week == bye, "note"] = "Bye"
    df.loc[(df.note == "") & ~df.played, "note"] = "Did not play"
    return df


def player_summary(data: LeagueData) -> pd.DataFrame:
    pw = data.player_weeks[data.player_weeks.week < data.current_week]
    started = pw[pw.is_starter]
    g = pw.groupby(["player_id", "name", "pos", "nfl_team"], dropna=False)
    df = g.agg(roster_total=("points", "sum"),
               games=("points", lambda s: (s != 0).sum())).reset_index()
    df["total"] = df.roster_total
    if data.has_nfl_stats:
        # Whole season from NFL stats: every game played, not just weeks on a league roster
        ps = data.player_stats
        ps = ps[ps.played & (ps.week < data.current_week)]
        df["total"] = df.player_id.map(ps.groupby("player_id").points.sum()).fillna(0)
        df["games"] = df.player_id.map(games_played(data)).fillna(0).astype(int)
    df["avg"] = df.total / df.games.where(df.games > 0)
    df["started"] = df.player_id.map(started.groupby("player_id").size()).fillna(0).astype(int)
    df["started_pts"] = df.player_id.map(started.groupby("player_id").points.sum()).fillna(0)
    # Fantasy team that has the player now; players dropped since are free agents
    owner_now = {pid: rid for rid, pids in data.current_rosters.items() for pid in pids}
    df["roster_id"] = df.player_id.map(owner_now)
    df["fantasy_team"] = df.roster_id.map(data.names).fillna("Free agent")
    return df.sort_values(["avg", "total"], ascending=False, na_position="last").reset_index(
        drop=True)


# ---------------------------------------------------------------- bye luck

REPLACEMENT_TOP_N = 5  # waiver value = median of the N best available free agents
REPLACEMENT_QUANTILE = 0.25  # fallback: this quantile of rostered players
UNAVAILABLE = {"IR", "Out", "PUP", "Sus", "DNR", "NA", "COV"}


def replacement_values(data: LeagueData, values: pd.Series | None = None) -> dict[str, float]:
    """Value of a realistic waiver-wire pickup per position (points per game).

    With Sleeper's weekly stats: the median of the best few healthy free agents who have
    played at least half the weeks so far (median, so one hot streak doesn't set it). Without them (fallback): the bottom quarter of
    currently rostered players, since free agents have no data then.
    """
    if values is None:
        values = player_values(data)
    rostered = {p for pids in data.current_rosters.values() for p in pids}
    by_pos: dict[str, list[float]] = {}
    for p in rostered:
        v = values.get(p)
        if v is not None and v > 0:
            by_pos.setdefault(data.player(p)["pos"], []).append(float(v))
    fallback = {pos: float(pd.Series(v).quantile(REPLACEMENT_QUANTILE))
                for pos, v in sorted(by_pos.items())}
    if not data.has_nfl_stats:
        return fallback

    gp = games_played(data)
    weeks_done = int(data.player_stats.week[data.player_stats.week < data.current_week].nunique())
    min_games = max(1, (weeks_done + 1) // 2)
    free_agents: dict[str, list[float]] = {}
    for p, v in values.items():
        info = data.player(p)
        if (p in rostered or not info.get("team") or gp.get(p, 0) < min_games
                or info.get("injury_status") in UNAVAILABLE):
            continue
        free_agents.setdefault(info["pos"], []).append(float(v))
    result = {}
    for pos in fallback:
        best = sorted(free_agents.get(pos, []), reverse=True)[:REPLACEMENT_TOP_N]
        result[pos] = float(pd.Series(best).median()) if best else fallback[pos]
    return result


def bye_luck(data: LeagueData) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Bye-week impact per team-week, for played and remaining regular-season weeks.

    Impact = best lineup with all players − best lineup without the players on bye,
    using each player's season average as their value. Both lineups may also use a
    waiver pickup at replacement level, so a team with no backup only loses the gap
    between its starter and the best waiver option.

    Returns (per team-week table, per player detail of who was on bye).
    """
    values = player_values(data)
    slots = starting_slots(data)
    repl = replacement_values(data, values)
    # Enough virtual waiver players per position to fill every slot if needed
    waiver = [(f"waiver:{pos}:{i}", [pos], v) for pos, v in repl.items()
              for i in range(len(slots))]

    def roster(week, rid):
        if week < data.current_week:
            return data.week_rosters.get((week, rid), [])
        return data.current_rosters.get(rid, [])

    cache = {}

    def impact(week, rid):
        key = (week, rid)
        if key not in cache:
            pids = roster(week, rid)
            on_bye = [p for p in pids if data.byes.get(data.player(p)["team"]) == week]
            cands = [(p, data.player(p)["fantasy_positions"], float(values.get(p, 0.0)))
                     for p in pids] + waiver
            full, starters = optimal_lineup(cands, slots)
            without, _ = optimal_lineup([c for c in cands if c[0] not in on_bye], slots)
            bye_starters = [p for p in on_bye if p in starters]
            cache[key] = {
                "count": len(on_bye),
                "value": sum(float(values.get(p, 0.0)) for p in on_bye),
                "impact": full - without,
                "players": on_bye,
                # For the breakdown: starters lost, and the loss if only waivers could fill in
                "starters": len(bye_starters),
                "starter_value": sum(float(values.get(p, 0.0)) for p in bye_starters),
                "no_bench": sum(max(float(values.get(p, 0.0))
                                    - repl.get(data.player(p)["pos"], 0.0), 0.0)
                                for p in bye_starters),
            }
        return cache[key]

    rows, detail = [], []
    for s in data.schedule.itertuples():
        if s.opp_roster_id is None or pd.isna(s.opp_roster_id):
            continue
        opp = int(s.opp_roster_id)
        own, other = impact(s.week, s.roster_id), impact(s.week, opp)
        rows.append({
            "week": s.week,
            "roster_id": s.roster_id,
            "opp_roster_id": opp,
            "played": s.week < data.current_week,
            "own_count": own["count"], "own_value": own["value"], "own_impact": own["impact"],
            "opp_count": other["count"], "opp_value": other["value"],
            "opp_impact": other["impact"],
            "net": other["impact"] - own["impact"],
            "own_starters": own["starters"], "own_starter_value": own["starter_value"],
            "own_no_bench": own["no_bench"],
        })
    for (week, rid), v in cache.items():
        for p in v["players"]:
            info = data.player(p)
            detail.append({"week": week, "roster_id": rid, "player_id": p, "name": info["name"],
                           "pos": info["pos"], "nfl_team": info["team"],
                           "avg": float(values.get(p, 0.0))})

    weekly = pd.DataFrame(rows, columns=[
        "week", "roster_id", "opp_roster_id", "played", "own_count", "own_value", "own_impact",
        "opp_count", "opp_value", "opp_impact", "net",
        "own_starters", "own_starter_value", "own_no_bench"])
    weekly["team"] = weekly.roster_id.map(data.names)
    weekly["opponent"] = weekly.opp_roster_id.map(data.names)
    detail = pd.DataFrame(detail, columns=["week", "roster_id", "player_id", "name", "pos",
                                           "nfl_team", "avg"])
    return weekly, detail


def bye_luck_summary(weekly: pd.DataFrame) -> pd.DataFrame:
    """Per team totals, split into played and remaining weeks."""
    cols = ["own_count", "own_value", "own_impact", "opp_count", "opp_value", "opp_impact", "net"]
    parts = []
    for played, label in ((True, "played"), (False, "remaining")):
        g = weekly[weekly.played == played].groupby(["roster_id", "team"])[cols].sum()
        parts.append(g.add_prefix(f"{label}_"))
    return pd.concat(parts, axis=1).fillna(0).reset_index()

def bye_breakdown(weekly: pd.DataFrame) -> pd.DataFrame:
    """Why each team loses what it does to its own byes (whole regular season).

    loss without bench = starters on bye replaced by waiver players only;
    bench saved = how much the team's own backups cut that down.
    """
    g = weekly.groupby(["roster_id", "team"]).agg(
        starters=("own_starters", "sum"),
        worst_week=("own_starters", "max"),
        starter_value=("own_starter_value", "sum"),
        no_bench=("own_no_bench", "sum"),
        lost=("own_impact", "sum"),
    ).reset_index()
    g["bench_saved"] = g.no_bench - g.lost
    return g.sort_values("lost", ascending=False).reset_index(drop=True)
