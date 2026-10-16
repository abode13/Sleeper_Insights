import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from sleeper import player_view, stats, theme

data = st.session_state["data"]
st.title("Teams")

names = data.names
rid = st.selectbox("Team", options=list(names), format_func=names.get)

tw = data.team_weeks
mine = tw[(tw.roster_id == rid) & tw.final]
if mine.empty:
    st.info("No completed weeks yet.")
    st.stop()

eff = stats.lineup_efficiency(data)
eff = eff[(eff.roster_id == rid) & (eff.week < data.current_week)]

c1, c2, c3, c4 = st.columns(4)
reg = mine[mine.regular]
c1.metric("Record", f"{(reg.result == 'W').sum()}-{(reg.result == 'L').sum()}")
c2.metric("Avg points", f"{mine.points.mean():.2f}")
best = mine.loc[mine.points.idxmax()]
c3.metric(f"Best week (W{best.week})", f"{best.points:.2f}")
c4.metric(f"Left on bench · {eff.efficiency.mean():.0%} efficiency",
          f"{eff.left_on_bench.sum():.1f}",
          help="Points an optimal lineup would have added (greedy best lineup each week)")

# -- Score vs. league median ---------------------------------------------------
st.subheader("Weekly score vs. league median")
medians = tw[tw.final].groupby("week").points.median()
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=medians.index, y=medians.values, name="League median", mode="lines",
    line=dict(color=theme.MUTED, width=2, dash="dot"),
    hovertemplate="Week %{x} median: %{y:.2f}<extra></extra>",
))
fig.add_trace(go.Scatter(
    x=mine.week, y=mine.points, name=names[rid], mode="lines+markers",
    line=dict(color=theme.HIGHLIGHT, width=2),
    marker=dict(size=9, color=theme.HIGHLIGHT, line=dict(color=theme.SURFACE, width=2)),
    customdata=mine[["opp_points", "result"]].assign(
        opp=mine.opp_roster_id.map(names)).to_numpy(),
    hovertemplate=("Week %{x}: <b>%{y:.2f}</b><br>%{customdata[1]} vs %{customdata[2]} "
                   "(%{customdata[0]:.2f})<extra></extra>"),
))
last = mine.iloc[-1]
fig.add_annotation(x=last.week, y=last.points, text=names[rid], showarrow=False,
                   xanchor="left", xshift=10, font=dict(color=theme.INK_2))
fig.update_layout(height=380, xaxis=dict(title="Week", dtick=1), yaxis_title="Points",
                  hovermode="x unified")
st.plotly_chart(fig, width="stretch")

left, right = st.columns(2)

# -- Starter points by position -------------------------------------------------
pw = data.player_weeks
pw = pw[(pw.roster_id == rid) & (pw.week < data.current_week)]
with left:
    st.subheader("Starter points by position")
    by_pos = pw[pw.is_starter].groupby("pos").points.sum().sort_values()
    fig = go.Figure(go.Bar(
        x=by_pos.values, y=by_pos.index, orientation="h", marker_color=theme.HIGHLIGHT,
        text=[f"{v:.0f}" for v in by_pos.values], textposition="outside",
        textfont=dict(color=theme.INK_2),
        hovertemplate="%{y}: %{x:.2f} pts<extra></extra>",
    ))
    fig.update_layout(height=320, xaxis_title="Points", bargap=0.35)
    st.plotly_chart(fig, width="stretch")

# -- Points left on the bench -------------------------------------------------------
with right:
    st.subheader("Points left on the bench")
    fig = go.Figure(go.Bar(
        x=eff.week, y=eff.left_on_bench, marker_color=theme.HIGHLIGHT,
        customdata=eff[["actual", "optimal"]].to_numpy(),
        hovertemplate=("Week %{x}: %{y:.2f} left on bench<br>"
                       "Actual %{customdata[0]:.2f} · optimal %{customdata[1]:.2f}"
                       "<extra></extra>"),
    ))
    fig.update_layout(height=320, xaxis=dict(title="Week", dtick=1), yaxis_title="Points",
                      bargap=0.35)
    st.plotly_chart(fig, width="stretch")

# -- Roster ----------------------------------------------------------------------------
st.subheader("Players")
current = set(data.current_rosters.get(rid, []))
agg = pw.groupby("player_id").agg(
    total=("points", "sum"),
    started=("is_starter", "sum"),
    starter_pts=("points", lambda s: s[pw.loc[s.index, "is_starter"]].sum()),
    weeks=("week", "nunique"),
)
ids = sorted(current | set(agg.index))
rows = []
for pid in ids:
    info = data.player(pid)
    a = agg.loc[pid] if pid in agg.index else None
    rows.append({
        "player_id": pid,
        "Player": info["name"], "Pos": info["pos"], "NFL": info["team"],
        "Bye": data.byes.get(info["team"]),
        "On roster": pid in current,
        "Total": a.total if a is not None else 0.0,
        "Avg": a.total / a.weeks if a is not None and a.weeks else 0.0,
        "Started": int(a.started) if a is not None else 0,
        "Starter pts": a.starter_pts if a is not None else 0.0,
        "Bench pts": max(a.total - a.starter_pts, 0.0) if a is not None else 0.0,
    })
roster = (pd.DataFrame(rows).sort_values(["On roster", "Total"], ascending=False)
          .reset_index(drop=True))
event = st.dataframe(
    roster.drop(columns="player_id"), hide_index=True, width="stretch",
    column_config={
        "Total": st.column_config.NumberColumn(format="%.2f"),
        "Avg": st.column_config.NumberColumn(format="%.2f", help="Per week on this roster"),
        "Starter pts": st.column_config.NumberColumn(format="%.2f"),
        "Bench pts": st.column_config.NumberColumn(format="%.2f"),
        "On roster": st.column_config.CheckboxColumn(help="On the roster today"),
    },
    on_select="rerun", selection_mode="single-cell",
    key=player_view.table_key("team_roster", rid),
)
st.caption("👆 Click a player to see his week-by-week stats.")
row = player_view.selected_row(event)
if row is not None and row < len(roster):
    player_view.show_player(data, roster.iloc[row].player_id)