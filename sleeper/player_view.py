"""Player detail popup, shared by the Players and Teams pages."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from sleeper import private, projections, statcols, stats, theme
from sleeper.model import LeagueData

RESET_KEY = "player_tables_reset"


def table_key(name: str, *filters) -> str:
    """Widget key for a clickable player table.

    It changes when the filters change or a player popup is closed, which gives a fresh
    table without a stale selection (Streamlit can't clear a selection otherwise).
    """
    return f"{name}_{hash(tuple(map(str, filters)))}_{st.session_state.get(RESET_KEY, 0)}"


def selected_row(event) -> int | None:
    sel = event.selection if event else None
    return sel.cells[0][0] if sel and sel.cells else None


def _reset_tables():
    st.session_state[RESET_KEY] = st.session_state.get(RESET_KEY, 0) + 1


def _projections(data: LeagueData, pid: str):
    """Projections row: Sleeper for everyone, FantasyPros only when unlocked."""
    weeks = projections.projection_weeks(data)
    if not weeks:
        return
    proj = projections.sleeper_projections(data).set_index("player_id")
    unlocked = private.is_unlocked()
    fp = (projections.fantasypros(data, private.fantasypros_key())[0] if unlocked
          else pd.DataFrame(columns=["player_id"])).set_index("player_id")

    def get(frame, col):
        v = frame[col].get(pid) if col in frame else None
        return None if v is None or pd.isna(v) else v

    with st.container(border=True):
        st.caption(f"Projections · week {weeks[0]} and rest of season (Sleeper, this "
                   "league's scoring)")
        c1, c2, c3, c4, c5 = st.columns(5)
        wk, ros = get(proj, "proj_week"), get(proj, "proj_ros")
        on_bye = data.byes.get(data.player(pid)["team"]) == weeks[0]
        c1.metric(f"Proj W{weeks[0]}", "Bye" if on_bye else f"{wk:.1f}" if wk is not None
                  else "–", help="Sleeper projection in this league's scoring")
        c2.metric("Proj rest of season", f"{ros:.1f}" if ros is not None else "–",
                  help=f"Sleeper projection, weeks {weeks[0]}–{data.last_regular_week}")
        if not unlocked:
            return
        if fp.empty:
            c3.caption("🔒 FantasyPros rankings appear once `FANTASYPROS_API_KEY` is set.")
            return
        def rank(ecr_col, pos_col):
            ecr, pos_rank = get(fp, ecr_col), get(fp, pos_col)
            if ecr is None and not pos_rank:
                return "–"
            return " · ".join(x for x in (f"#{ecr:.0f}" if ecr is not None else "",
                                          pos_rank or "") if x)

        fp_pts = get(fp, "fp_proj")
        c3.metric(f"🔒 FP proj W{weeks[0]}", f"{fp_pts:.1f}" if fp_pts is not None else "–",
                  help="Private · FantasyPros projection, this week (half PPR)")
        c4.metric(f"🔒 ECR W{weeks[0]}", rank("fp_ecr", "fp_pos_rank"),
                  help="Private · FantasyPros consensus rank · position rank, this week")
        c5.metric("🔒 ECR ROS", rank("fp_ros_ecr", "fp_ros_pos_rank"),
                  help="Private · FantasyPros consensus rank · position rank, rest of season")
        st.caption("🔒 only visible to you · Rankings & projections: FantasyPros.")


@st.dialog("Player", width="large", on_dismiss=_reset_tables)
def show_player(data: LeagueData, pid: str):
    info = data.player(pid)
    detail = stats.player_weekly_detail(data, pid)
    owner = {p: rid for rid, pids in data.current_rosters.items() for p in pids}.get(pid)
    pw = data.player_weeks
    on_rosters = pw[(pw.player_id == pid) & (pw.week < data.current_week)].points.sum()
    played = detail[detail.points.notna()]

    st.subheader(f"{info['name']} · {info['pos']} · {info['team'] or 'no NFL team'}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Games played", len(played))
    m2.metric("Points per game", f"{played.points.mean():.2f}" if len(played) else "–")
    m3.metric("Fantasy team now", data.team_name(owner) if owner else "Free agent")
    m4.metric("Points on league rosters", f"{on_rosters:.1f}",
              help="Points scored while on any roster in this league, bench included")
    _projections(data, pid)

    fig = go.Figure(go.Bar(
        x=played.week, y=played.points, marker_color=theme.HIGHLIGHT,
        hovertemplate="Week %{x}: %{y:.2f} pts<extra></extra>",
    ))
    fig.update_layout(height=240, xaxis=dict(title="Week", dtick=1), yaxis_title="Points",
                      bargap=0.35, margin=dict(t=10))
    st.plotly_chart(fig, width="stretch")

    base = ["week", "opponent", "result", "fantasy_team", "started", "points"]
    keys = [c for c in detail.columns if c not in base and c != "played"]

    def stat_column(k):
        pts = data.scoring.get(k)
        return st.column_config.TextColumn(
            statcols.label(k), alignment="right",
            help=f"Scored in this league: {pts:+g} pts each" if pts else "Not scored")

    # Pre-formatted text so missed weeks show blank cells (number columns would say "None")
    table = detail[base + keys].copy()
    for k in ["points"] + keys:
        fmt = "{:.2f}" if k == "points" else (
            "{:.0f}" if (table[k].dropna() % 1 == 0).all() else "{:.1f}")
        table[k] = table[k].map(lambda v, f=fmt: "" if pd.isna(v) else f.format(v))
    st.dataframe(
        theme.shade(table, ["points"] + keys, values=detail,
                    lower_is_better=statcols.lower_is_better(keys, data.scoring)),
        hide_index=True, width="stretch",
        column_config={
            "week": "Week", "opponent": "Opponent",
            "result": st.column_config.TextColumn(
                "Result", help="NFL game result for his team · DNP = did not play"),
            "fantasy_team": "Fantasy team",
            "started": st.column_config.CheckboxColumn("Started"),
            "points": st.column_config.TextColumn("Points", alignment="right"),
            **{k: stat_column(k) for k in keys},
        },
    )
    st.caption("Hover a stat's header to see how many points it's worth in this league.")
