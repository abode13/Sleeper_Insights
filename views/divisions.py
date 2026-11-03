import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from sleeper import projections, stats, theme

data = st.session_state["data"]
st.title("Division ranking")

table = stats.standings(data)
if not data.divisions or table.division.isna().all():
    st.info("This league has no divisions.")
    st.stop()
if table[["W", "L", "T"]].to_numpy().sum() == 0:
    st.info("No completed weeks yet.")
    st.stop()

team_proj = projections.team_projections(data)
summary = stats.division_summary(data, table, team_proj)
matchups = stats.division_matchups(data)
tw = stats.division_team_weeks(data)
tw = tw[tw["div"].notna()]

div_name = {d: info["name"] for d, info in data.divisions.items()}
# Stable color per division (by division number), shared by every chart on this page
div_color = {d: theme.SERIES[i % len(theme.SERIES)]
             for i, d in enumerate(sorted(data.divisions))}


def record(w, l, t=0) -> str:
    return f"{int(w)}-{int(l)}" + (f"-{int(t)}" if t else "")


summary["Record"] = [record(r.W, r.L, r.T) for r in summary.itertuples()]
summary["Non-div"] = [record(w, l, t) for w, l, t in zip(
    summary["Non-div W"], summary["Non-div L"], summary["Non-div T"])]

# -- Leaders -------------------------------------------------------------------------------
best = summary.iloc[0]
top_pf = summary.loc[summary["Avg PF"].idxmax()]
top_cross = summary.loc[summary["Non-div %"].fillna(-1).idxmax()]
c1, c2, c3 = st.columns(3)
c1.metric("Strongest division", best.Division,
          help="Highest all-play %: how often its teams would beat a random league team "
               "in the same week, so schedule luck doesn't count")
c2.metric("Highest scoring", top_pf.Division, f"{top_pf['Avg PF']:.2f} per game",
          delta_color="off")
if pd.notna(top_cross["Non-div %"]):
    c3.metric("Best vs. other divisions", top_cross.Division,
              f"{top_cross['Non-div']} ({top_cross['Non-div %']:.0%})", delta_color="off")

# -- Ranking table -----------------------------------------------------------------------
st.subheader("Ranking")
RANK_COLS = ["Rank"] + (["avatar"] if summary.avatar.notna().any() else []) + [
    "Division", "Teams", "Record", "Non-div", "Non-div %", "AP %", "Med %",
    "Avg PF", "Avg PA", "Playoff", "Avg rank", "Best rank"]
SCORING_COLS = ["Division", "Avg PF", "Med PF", "Avg PA", "Med PA", "PF / team", "Std",
                "Best", "Worst", "Top weeks", "Bottom weeks", "Luck", "Efficiency", "vs Proj"]
if team_proj.empty:
    SCORING_COLS.remove("vs Proj")

LOWER_IS_BETTER = ["Avg PA", "Med PA", "Avg rank", "Best rank", "Bottom weeks", "Std"]
FORMATS = {
    "Non-div %": "{:.0%}", "AP %": "{:.0%}", "Med %": "{:.0%}", "Efficiency": "{:.1%}",
    "Avg PF": "{:.2f}", "Med PF": "{:.2f}", "Avg PA": "{:.2f}", "Med PA": "{:.2f}",
    "PF / team": "{:.1f}", "Std": "{:.1f}", "Best": "{:.2f}", "Worst": "{:.2f}",
    "Avg rank": "{:.1f}", "Luck": "{:+.2f}", "vs Proj": "{:+.2f}",
}
HELP = {
    "avatar": st.column_config.ImageColumn("", width="small"),
    "Teams": st.column_config.Column("Teams", help="Teams in the division"),
    "Record": st.column_config.Column(
        "Record", help="Combined H2H record (games between division rivals count both ways)"),
    "Non-div": st.column_config.Column(
        "Non-div", help="Combined record against teams from other divisions"),
    "Non-div %": st.column_config.Column("Non-div %", help="Win % against other divisions"),
    "AP %": st.column_config.Column(
        "All-play %", help="Share of games its teams would win playing every team every "
                           "week. The ranking uses this: it ignores schedule luck"),
    "Med %": st.column_config.Column("Median %", help="Share of weeks above the league median"),
    "Avg PF": st.column_config.Column("Avg PF", help="Mean points scored per team-week"),
    "Med PF": st.column_config.Column("Med PF", help="Median points scored per team-week"),
    "Avg PA": st.column_config.Column("Avg PA", help="Mean points allowed per team-week"),
    "Med PA": st.column_config.Column("Med PA", help="Median points allowed per team-week"),
    "PF / team": st.column_config.Column("PF / team", help="Season points for, per team"),
    "Std": st.column_config.Column(
        "Std dev", help="Spread of weekly scores. Lower = more consistent"),
    "Best": st.column_config.Column("Best week", help="Highest single-week score"),
    "Worst": st.column_config.Column("Worst week", help="Lowest single-week score"),
    "Top weeks": st.column_config.Column(
        "Top weeks", help="Weeks in which a division team had the league's highest score"),
    "Bottom weeks": st.column_config.Column(
        "Bottom weeks", help="Weeks in which a division team had the league's lowest score"),
    "Playoff": st.column_config.Column(
        "Playoff", help="Playoff spots if the season ended today"),
    "Avg rank": st.column_config.Column("Avg rank", help="Mean league standing of its teams"),
    "Best rank": st.column_config.Column("Best rank", help="League standing of its best team"),
    "Luck": st.column_config.Column(
        "Luck", help="Mean per team: actual H2H wins − wins expected from all-play"),
    "Efficiency": st.column_config.Column(
        "Lineup eff.", help="Started points ÷ best possible lineup points"),
    "vs Proj": st.column_config.Column(
        "vs Proj", help="Mean per team-week: actual − Sleeper-projected points of the "
                        "lineup that was started"),
}


def show(cols):
    numeric = [c for c in cols if c in FORMATS or c in (
        "Top weeks", "Bottom weeks", "Playoff", "Best rank")]
    df = summary[cols]
    styled = theme.shade(df, numeric, lower_is_better=[c for c in LOWER_IS_BETTER if c in cols])
    styled = styled.format({c: f for c, f in FORMATS.items() if c in cols}, na_rep="–")
    st.dataframe(styled, hide_index=True, width="stretch", height=35 * (len(df) + 1) + 3,
                 column_config={c: v for c, v in HELP.items() if c in cols})


show(RANK_COLS)
st.caption("Ranked by all-play %, then average points for. Green = best division in that "
           "column, red = worst.")

st.subheader("Scoring")
show(SCORING_COLS)
st.caption("Per team-week numbers, so divisions with different team counts compare fairly. "
           "Completed regular-season weeks only.")

# -- Head-to-head between divisions -------------------------------------------------------
st.subheader("Head-to-head between divisions")
divs = list(summary.division)
labels = [div_name[d] for d in divs]
z, text = [], []
for d in divs:
    zrow, trow = [], []
    for o in divs:
        m = matchups[(matchups["div"] == d) & (matchups.opp_div == o)]
        if d == o or m.empty:
            zrow.append(None)
            trow.append("—" if d == o else "no games")
            continue
        m = m.iloc[0]
        zrow.append((m.W + 0.5 * m["T"]) / m.games)
        trow.append(f"{record(m.W, m.L, m['T'])}<br>{m.PF - m.PA:+.0f} pts")
    z.append(zrow)
    text.append(trow)
fig = go.Figure(go.Heatmap(
    z=z, x=labels, y=labels, text=text, texttemplate="%{text}",
    textfont=dict(color=theme.INK, size=13),
    colorscale=theme.DIVERGING, zmin=0, zmax=1, zmid=0.5, xgap=3, ygap=3,
    colorbar=dict(title="Win %", thickness=12, tickformat=".0%"),
    hovertemplate="<b>%{y}</b> vs %{x}<br>%{text}<extra></extra>",
))
fig.update_layout(height=max(260, 90 * len(labels) + 80), yaxis=dict(autorange="reversed"),
                  xaxis=dict(side="top"), plot_bgcolor=theme.SURFACE)
st.plotly_chart(fig, width="stretch")
st.caption("Read across: the row division's record and point difference against the "
           "column division.")

# -- Score distribution -----------------------------------------------------------------
left, right = st.columns(2)
with left:
    st.subheader("Weekly scores")
    fig = go.Figure()
    for d in divs:
        g = tw[tw["div"] == d]
        fig.add_trace(go.Box(
            y=g.points, name=div_name[d], boxpoints="all", jitter=0.35, pointpos=0,
            marker=dict(color=div_color[d], size=6, line=dict(color=theme.SURFACE, width=1)),
            line=dict(color=div_color[d], width=2), boxmean=True,
            customdata=g[["team", "week"]].to_numpy(),
            hovertemplate="<b>%{customdata[0]}</b><br>Week %{customdata[1]}: "
                          "%{y:.2f}<extra></extra>",
        ))
    fig.update_layout(height=420, yaxis_title="Points", showlegend=False)
    st.plotly_chart(fig, width="stretch")
    st.caption("Every team-week score. Box = middle half, line = median, dashed = mean.")

with right:
    st.subheader("Team strength")
    fig = go.Figure()
    for d in divs:
        t = table[table.division == d]
        fig.add_trace(go.Scatter(
            x=[div_name[d]] * len(t), y=t["AP %"], mode="markers", name=div_name[d],
            marker=dict(size=13, color=div_color[d], line=dict(color=theme.SURFACE, width=2)),
            customdata=t[["team", "Avg PF"]].to_numpy(),
            hovertemplate="<b>%{customdata[0]}</b><br>All-play %{y:.0%}<br>"
                          "Avg PF %{customdata[1]:.2f}<extra></extra>",
        ))
    fig.add_hline(0.5, line=dict(color=theme.AXIS, dash="dot", width=1))
    fig.update_layout(height=420, yaxis=dict(title="All-play %", tickformat=".0%"),
                      showlegend=False)
    st.plotly_chart(fig, width="stretch")
    st.caption("One dot per team. Above the dotted line = better than a league-average team.")

# -- Weekly trend --------------------------------------------------------------------------
st.subheader("Average score per week")
weekly = tw.groupby(["week", "div"]).points.mean().unstack("div")
league = tw.groupby("week").points.mean()
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=league.index, y=league.values, name="League", mode="lines",
    line=dict(color=theme.MUTED, width=2, dash="dot"),
    hovertemplate="League: %{y:.2f}<extra></extra>",
))
for d in divs:
    if d not in weekly:
        continue
    fig.add_trace(go.Scatter(
        x=weekly.index, y=weekly[d], name=div_name[d], mode="lines+markers",
        line=dict(color=div_color[d], width=2),
        marker=dict(size=7, color=div_color[d], line=dict(color=theme.SURFACE, width=1)),
        hovertemplate=f"{div_name[d]}: " + "%{y:.2f}<extra></extra>",
    ))
fig.update_layout(height=380, xaxis=dict(title="Week", dtick=1), yaxis_title="Points",
                  hovermode="x unified")
st.plotly_chart(fig, width="stretch")

# -- Teams --------------------------------------------------------------------------------
st.subheader("Teams by division")
for d in divs:
    t = table[table.division == d]
    t = t.assign(Record=[record(r.W, r.L, r.T) for r in t.itertuples()])
    with st.expander(f"{div_name[d]} · {len(t)} teams"):
        st.dataframe(
            t[["Rank", "team", "owner", "Record", "PF", "PA", "Avg PF", "AP %", "Luck"]],
            hide_index=True, width="stretch",
            column_config={
                "Rank": st.column_config.NumberColumn("League rank"),
                "team": "Team", "owner": "Manager",
                "PF": st.column_config.NumberColumn(format="%.2f"),
                "PA": st.column_config.NumberColumn(format="%.2f"),
                "Avg PF": st.column_config.NumberColumn(format="%.2f"),
                "AP %": st.column_config.ProgressColumn(
                    "All-play %", format="percent", min_value=0, max_value=1),
                "Luck": st.column_config.NumberColumn(format="%+.1f"),
            },
        )
