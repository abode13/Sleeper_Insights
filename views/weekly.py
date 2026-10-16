import plotly.graph_objects as go
import streamlit as st

from sleeper import theme

data = st.session_state["data"]
st.title("Weekly")

tw = data.team_weeks
if tw.empty:
    st.info("No scores yet this season.")
    st.stop()

weeks = sorted(tw.week.unique())
week = st.select_slider("Week", options=weeks, value=weeks[-1])
g = tw[tw.week == week]
live = not g.final.iloc[0]
if live:
    st.caption("🔴 Week in progress — scores are live.")

top, low = g.loc[g.points.idxmax()], g.loc[g.points.idxmin()]
c1, c2, c3 = st.columns(3)
c1.metric("League median", f"{g.points.median():.2f}")
c2.metric(f"High score · {top.team}", f"{top.points:.2f}")
c3.metric(f"Low score · {low.team}", f"{low.points:.2f}")

st.subheader("Matchups")
seen, pairs = set(), []
for r in g.sort_values("matchup_id").itertuples():
    if r.roster_id in seen:
        continue
    seen.update({r.roster_id, r.opp_roster_id})
    pairs.append(r)

cols = st.columns(3)
median = g.points.median()
for i, r in enumerate(pairs):
    with cols[i % 3].container(border=True):
        sides = [(r.team, r.points)]
        if r.opp_roster_id is not None and r.opp_points == r.opp_points:  # not NaN
            sides.append((data.team_name(r.opp_roster_id), r.opp_points))
        best = max(p for _, p in sides)
        for name, pts in sides:
            mark = "✓ " if pts == best and len(sides) == 2 and not live else ""
            med = " · *beat median*" if pts > median else ""
            weight = "**" if mark else ""
            st.markdown(f"{weight}{mark}{name}{weight} — {weight}{pts:.2f}{weight}{med}")

st.subheader("Score distribution by week")
tw = tw[tw.final]  # a live week would skew the picture
fig = go.Figure(go.Box(
    x=tw.week, y=tw.points, boxpoints="all", jitter=0.3, pointpos=0,
    marker=dict(color=theme.HIGHLIGHT, size=8, line=dict(color=theme.SURFACE, width=1)),
    line=dict(color=theme.HIGHLIGHT, width=2), fillcolor="rgba(42,120,214,0.12)",
    customdata=tw.team, name="Scores",
    hovertemplate="<b>%{customdata}</b><br>Week %{x}: %{y:.2f}<extra></extra>",
))
medians = tw.groupby("week").points.median()
fig.add_trace(go.Scatter(
    x=medians.index, y=medians.values, mode="lines", name="Weekly median",
    line=dict(color=theme.INK_2, width=2, dash="dot"),
    hovertemplate="Week %{x} median: %{y:.2f}<extra></extra>",
))
fig.update_layout(height=420, xaxis=dict(title="Week", dtick=1), yaxis_title="Points")
st.plotly_chart(fig, width="stretch")