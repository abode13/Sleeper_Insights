import plotly.graph_objects as go
import streamlit as st

from sleeper import stats, theme

data = st.session_state["data"]
st.title("Bye luck")
st.markdown(
    "How much did byes help or hurt you? For each week we take the **best possible lineup** "
    "with every rostered player valued at his season average (points per game in this "
    "league's scoring), then again **without the players on bye**. The difference is the "
    "points that team lost to byes.\n\n"
    "A bench player steps in where possible, and so can a **waiver pickup** at replacement "
    "level — so a team with only one defense or QB loses the gap to the best waiver option, "
    "not the whole score.\n\n"
    "**Net bye luck = points your opponents lost − points you lost.** Positive is good for you. "
    "Remaining weeks use today's rosters, so they shift with trades and waiver moves."
)
if not data.byes:
    st.warning("NFL bye weeks for this season couldn't be loaded.")
    st.stop()

repl = stats.replacement_values(data)
if repl:
    with st.expander("Waiver replacement values (points per game)"):
        st.caption("Estimated best free agent per position: the bottom quarter of rostered "
                   "players at that position (Sleeper doesn't report free-agent points).")
        st.dataframe({pos: [round(v, 1)] for pos, v in repl.items()}, hide_index=True)

weekly, detail = stats.bye_luck(data)
if weekly.empty:
    st.info("No regular-season schedule found.")
    st.stop()

summary = stats.bye_luck_summary(weekly)
for part in ("played", "remaining"):
    for col in ("own_count", "own_impact", "opp_count", "opp_impact", "net"):
        if f"{part}_{col}" not in summary:
            summary[f"{part}_{col}"] = 0.0
summary["total_own_impact"] = summary.played_own_impact + summary.remaining_own_impact
summary["total_opp_impact"] = summary.played_opp_impact + summary.remaining_opp_impact
summary["total_net"] = summary.played_net + summary.remaining_net
summary = summary.sort_values("total_net", ascending=False)

PERIODS = {"played": ("P", "weeks played"), "remaining": ("R", "rest of season, projected"),
           "total": ("S", "whole season: played + rest")}
# column -> (short header, hover text, format)
show = {"team": ("Team", None, None)}
for part, (tag, period) in PERIODS.items():
    if part != "total":
        show[f"{part}_own_count"] = (f"Own # {tag}", f"Your players on bye ({period})", "%d")
    show[f"{part}_own_impact"] = (f"Own {tag}", f"Points your lineup lost to byes ({period})",
                                  "%.1f")
    if part != "total":
        show[f"{part}_opp_count"] = (f"Opp # {tag}",
                                     f"Your opponents' players on bye ({period})", "%d")
    show[f"{part}_opp_impact"] = (f"Opp {tag}",
                                  f"Points your opponents lost to byes ({period})", "%.1f")
    show[f"{part}_net"] = (f"Net {tag}", f"Opp lost − own lost ({period}). Positive = lucky",
                           "%+.1f")
cols = list(show)

st.subheader("Season overview")
st.caption("**P** = weeks played · **R** = rest of season (projected) · **S** = whole season. "
           "**#** = players on bye, otherwise points lost. Hover a header for details.")
st.dataframe(
    summary[cols].rename(columns={c: v[0] for c, v in show.items()}),
    hide_index=True, width="stretch", height=35 * (len(summary) + 1) + 3,
    column_config={
        label: st.column_config.NumberColumn(label, help=help_, format=fmt)
        for c, (label, help_, fmt) in show.items() if fmt
    },
)

# -- Breakdown: why teams lose what they lose -----------------------------------------
st.subheader("Why some teams lose more")
st.caption("Your own byes over the whole season. Losses grow with **better starters** on bye, "
           "**stacked** byes (many starters out in one week) and a **thin bench**.")
breakdown = stats.bye_breakdown(weekly)
st.dataframe(
    breakdown[["team", "starters", "worst_week", "starter_value", "no_bench", "lost",
               "bench_saved"]],
    hide_index=True, width="stretch", height=35 * (len(breakdown) + 1) + 3,
    column_config={
        "team": "Team",
        "starters": st.column_config.NumberColumn(
            "Starters", help="Starters on bye over the whole season"),
        "worst_week": st.column_config.NumberColumn(
            "Max/wk", help="Most starters on bye in a single week (stacked byes)"),
        "starter_value": st.column_config.NumberColumn(
            "Value", format="%.1f",
            help="Combined points per game of those starters — how good they are"),
        "no_bench": st.column_config.NumberColumn(
            "No bench", format="%.1f",
            help="Points lost if every starter on bye were replaced by a waiver pickup"),
        "lost": st.column_config.NumberColumn(
            "Lost", format="%.1f", help="Points actually lost, using your bench too"),
        "bench_saved": st.column_config.NumberColumn(
            "Bench saved", format="%.1f",
            help="How much your own backups cut the loss (No bench − Lost)"),
    },
)

# -- Heatmap: team x week ---------------------------------------------------------------
st.subheader("Net bye impact by week")
grid = weekly.pivot_table(index="team", columns="week", values="net", aggfunc="sum")
grid = grid.reindex(summary.team)
weeks = list(grid.columns)
x = [f"W{w}" if w < data.current_week else f"W{w}*" for w in weeks]
opp_names = weekly.pivot_table(index="team", columns="week", values="opponent",
                               aggfunc="first").reindex(index=grid.index, columns=weeks)
lim = max(abs(grid.min().min()), abs(grid.max().max()), 1)
fig = go.Figure(go.Heatmap(
    z=grid.to_numpy(), x=x, y=grid.index, customdata=opp_names.to_numpy(),
    colorscale=theme.DIVERGING, zmid=0, zmin=-lim, zmax=lim, xgap=2, ygap=2,
    colorbar=dict(title="Net", thickness=12),
    hovertemplate="<b>%{y}</b> vs %{customdata}<br>%{x}: %{z:+.1f} pts<extra></extra>",
))
played_weeks = [w for w in weeks if w < data.current_week]
if played_weeks and len(played_weeks) < len(weeks):
    fig.add_vline(x=len(played_weeks) - 0.5, line=dict(color=theme.INK_2, width=2, dash="dot"))
    fig.add_annotation(x=len(played_weeks) - 0.5, y=1.02, yref="paper", text="projected →",
                       showarrow=False, xanchor="left", font=dict(color=theme.MUTED, size=11))
fig.update_layout(height=max(320, 34 * len(grid) + 100), yaxis=dict(autorange="reversed"))
st.plotly_chart(fig, width="stretch")
st.caption("Blue: byes hurt your opponent more than you. Red: byes hurt you more. "
           "\\* = projected with current rosters.")

# -- Drill-down ----------------------------------------------------------------------------
st.subheader("Who was on bye?")
names = data.names
c1, c2 = st.columns(2)
rid = c1.selectbox("Team", list(names), format_func=names.get, key="bye_team")
team_weeks = weekly[weekly.roster_id == rid]
active = team_weeks[(team_weeks.own_count > 0) | (team_weeks.opp_count > 0)]
if active.empty:
    st.info("No byes affecting this matchup schedule.")
    st.stop()
week = c2.selectbox("Week", list(active.week),
                    format_func=lambda w: f"Week {w}" + ("" if w < data.current_week
                                                          else " (projected)"))
row = active[active.week == week].iloc[0]

left, right = st.columns(2)
for col, label, team_id, impact in (
    (left, names[rid], rid, row.own_impact),
    (right, f"Opponent: {names.get(row.opp_roster_id, '?')}", row.opp_roster_id,
     row.opp_impact),
):
    with col:
        st.markdown(f"**{label}** — lineup lost **{impact:.1f}** pts")
        players = detail[(detail.week == week) & (detail.roster_id == team_id)]
        if players.empty:
            st.caption("Nobody on bye.")
        else:
            st.dataframe(
                players[["name", "pos", "nfl_team", "avg"]].sort_values("avg", ascending=False),
                hide_index=True, width="stretch",
                column_config={"name": "Player", "pos": "Pos", "nfl_team": "NFL",
                               "avg": st.column_config.NumberColumn("Avg pts", format="%.2f")},
            )