import plotly.graph_objects as go
import streamlit as st

from sleeper import stats, theme

data = st.session_state["data"]
st.title("Players")
st.caption("Only points scored while on a fantasy roster in this league are counted "
           "(Sleeper doesn't report points for free agents).")

summary = stats.player_summary(data)
if summary.empty:
    st.info("No completed weeks yet.")
    st.stop()

f1, f2, f3 = st.columns([2, 3, 1])
positions = sorted(summary.pos.dropna().unique())
pos = f1.multiselect("Position", positions, placeholder="All positions")
teams = sorted(summary.fantasy_team.unique())
team = f2.multiselect("Fantasy team", teams, placeholder="All teams")
min_games = f3.number_input("Min games", 0, 18, 1)

view = summary
if pos:
    view = view[view.pos.isin(pos)]
if team:
    view = view[view.fantasy_team.isin(team)]
view = view[view.games >= min_games]

st.dataframe(
    view[["name", "pos", "nfl_team", "fantasy_team", "total", "games", "avg", "started",
          "started_pts"]],
    hide_index=True, width="stretch", height=420,
    column_config={
        "name": "Player", "pos": "Pos", "nfl_team": "NFL", "fantasy_team": "Fantasy team",
        "total": st.column_config.NumberColumn("Total", format="%.2f"),
        "games": st.column_config.NumberColumn("Games", help="Weeks with non-zero points"),
        "avg": st.column_config.NumberColumn("Avg", format="%.2f"),
        "started": "Started",
        "started_pts": st.column_config.NumberColumn("Pts as starter", format="%.2f"),
    },
)

st.subheader("Weekly points — top players")
n = st.slider("Players shown", 10, 50, 25, step=5)
top = view.head(n)
pw = data.player_weeks
pw = pw[pw.player_id.isin(top.player_id) & (pw.week < data.current_week)]
grid = (pw.groupby(["player_id", "week"]).points.sum().unstack("week")
        .reindex(top.player_id).replace(0, float("nan")))
labels = [f"{r.name} ({r.pos})" for r in top.itertuples()]
fig = go.Figure(go.Heatmap(
    z=grid.to_numpy(), x=[f"W{w}" for w in grid.columns], y=labels,
    colorscale=[[i / (len(theme.SEQUENTIAL) - 1), c] for i, c in enumerate(theme.SEQUENTIAL)],
    xgap=2, ygap=2, colorbar=dict(title="Pts", thickness=12),
    hovertemplate="%{y}<br>%{x}: %{z:.2f} pts<extra></extra>",
))
fig.update_layout(height=max(300, 24 * len(labels) + 80), yaxis=dict(autorange="reversed"),
                  plot_bgcolor=theme.SURFACE)
st.plotly_chart(fig, width="stretch")
st.caption("Blank cells: not on a fantasy roster that week, or a bye.")