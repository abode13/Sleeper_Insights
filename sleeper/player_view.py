"""Player detail popup, shared by the Players and Teams pages."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from sleeper import statcols, stats, theme
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
