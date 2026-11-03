import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from sleeper import bracket, projections, stats, theme

data = st.session_state["data"]
st.title("Standings")

table = stats.standings(data)
if table.empty or table[["W", "L", "T"]].to_numpy().sum() == 0:
    st.info("No completed weeks yet.")
    st.stop()

bye_weekly, _ = stats.bye_luck(data)
bye_played = bye_weekly[bye_weekly.played].groupby("roster_id").net.sum()
table["Bye luck"] = table.roster_id.map(bye_played).fillna(0)

table["Record"] = table.W.astype(str) + "-" + table.L.astype(str)
table.loc[table["T"] > 0, "Record"] += "-" + table["T"].astype(str)
table["Median"] = table["Med W"].astype(str) + "-" + table["Med L"].astype(str)
table["All-play"] = table["AP W"].map("{:g}".format) + "-" + table["AP L"].map("{:g}".format)

table["Div rec"] = table["Div W"].astype(str) + "-" + table["Div L"].astype(str)
if data.median_game:
    table["Total"] = table["Tot W"].astype(str) + "-" + table["Tot L"].astype(str)
has_divisions = bool(data.divisions) and table.division.notna().any()
if has_divisions:
    table["Division"] = table.division.map(lambda d: data.divisions.get(d, {}).get("name"))

COLUMN_CONFIG = {
    "avatar": st.column_config.ImageColumn("", width="small"),
    "team": "Team",
    "owner": "Manager",
    "Div rec": st.column_config.TextColumn("Div", help="Record against division rivals"),
    "Median": st.column_config.TextColumn(
        "Median", help="Record vs. the league median score each week"),
    "Total": st.column_config.TextColumn("Total", help="H2H + median games"),
    "PF": st.column_config.NumberColumn("PF", format="%.2f"),
    "PA": st.column_config.NumberColumn("PA", format="%.2f"),
    "Avg PF": st.column_config.NumberColumn("Avg PF", format="%.2f"),
    "All-play": st.column_config.TextColumn(
        "All-play", help="Record if you had played every team every week"),
    "AP %": st.column_config.ProgressColumn(
        "All-play %", format="percent", min_value=0, max_value=1,
        help="Share of games you'd have won playing every team every week"),
    "Luck": st.column_config.NumberColumn(
        "Luck", format="%+.1f",
        help="Actual H2H wins − expected wins from the all-play record"),
    "Bye luck": st.column_config.NumberColumn(
        "Bye luck", format="%+.1f",
        help="Points opponents lost to byes − points you lost to byes (played weeks). "
             "See the Bye luck page."),
}


def show_table(df, extra_cols=()):
    cols = ["Rank"] + (["avatar"] if df.avatar.notna().any() else []) + ["team", "owner"]
    cols += list(extra_cols) + ["Record", "Median"] + (["Total"] if data.median_game else [])
    cols += ["PF", "PA", "Avg PF", "All-play", "AP %", "Luck", "Bye luck"]
    st.dataframe(df[cols], hide_index=True, width="stretch",
                 height=35 * (len(df) + 1) + 3, column_config=COLUMN_CONFIG)


with st.popover("ℹ️ What do the columns mean?"):
    explanations = [
        "**Record** – head-to-head wins and losses.",
        "**Div** – record against your own division rivals.",
        "**Median** – record against the league median: a win for every week you scored "
        "more than half the league.",
        "**Total** – head-to-head plus median games (this league counts both)."
        if data.median_game else None,
        "**All-play** – your record if you had played *every* team *every* week. Scoring "
        "3rd-most in a 12-team week counts as 9-2 that week. It shows how strong a team "
        "really is, without the luck of the schedule.",
        "**All-play %** – share of those all-play games you won.",
        "**Luck** – actual wins minus the wins your all-play % would predict. Positive "
        "means you won more than your scores deserved.",
        "**Bye luck** – points your opponents lost to byes minus points you lost "
        "(weeks played). Details on the Bye luck page.",
    ]
    st.markdown("\n".join(f"- {e}" for e in explanations if e))

tab_names = ["League"] + (["Divisions"] if has_divisions else []) + ["Playoff picture"]
tabs = dict(zip(tab_names, st.tabs(tab_names)))

with tabs["League"]:
    show_table(table, extra_cols=["Division"] if has_divisions else [])

if has_divisions:
    with tabs["Divisions"]:
        for d, info in sorted(data.divisions.items()):
            div = table[table.division == d].copy()
            # Already sorted by overall standing, so the first row leads the division
            div["Rank"] = range(1, len(div) + 1)
            div.iloc[0, div.columns.get_loc("team")] = "👑 " + div.iloc[0]["team"]
            head = st.columns([1, 20], vertical_alignment="center")
            if info["avatar"]:
                head[0].image(info["avatar"], width=40)
            head[1].markdown(f"#### {info['name']}")
            show_table(div, extra_cols=["Div rec"])

with tabs["Playoff picture"]:
    seeds, pairs = stats.playoff_picture(data, table)
    st.markdown(f"**If the season ended today** — {data.playoff_teams} teams make the playoffs"
                + (" (every division leader is in and takes a top seed)." if has_divisions
                   else "."))
    rec_col = "Total" if data.median_game else "Record"
    bracket_teams = {
        int(r.Seed): {"team": r.team, "record": r[rec_col], "avatar": r.avatar,
                      "leader": r.Status.startswith("Division leader") or not has_divisions}
        for _, r in seeds[seeds.Seed.notna()].iterrows()
    }
    # Rendered in a frame because st.html sanitizes SVG away. All team names and image
    # URLs are HTML-escaped in bracket_svg, since they come from Sleeper users.
    st.iframe(
        '<!doctype html><body style="margin:0">'
        + bracket.bracket_svg(bracket_teams, data.playoff_teams, data.last_regular_week + 1,
                              data.playoff_round_type)
        + "</body>",
        height=bracket.bracket_height(data.playoff_teams) + 8,
    )
    if has_divisions:
        st.caption("Blue seed = division leader · gray seed = wildcard")
    pcols = ["Seed"] + (["avatar"] if seeds.avatar.notna().any() else []) + ["team", "owner"]
    pcols += (["Division"] if has_divisions else []) + [rec_col, "PF", "PA", "Status", "GB"]
    # Show blanks instead of "None" for teams without a seed / teams already in
    view = seeds[pcols].copy()
    view["Seed"] = view.Seed.map(lambda s: "" if pd.isna(s) else f"{s:.0f}")
    view["GB"] = view.GB.map(lambda g: "" if pd.isna(g) else f"{g:g}")
    st.dataframe(
        view, hide_index=True, width="stretch", height=35 * (len(view) + 1) + 3,
        column_config={
            **COLUMN_CONFIG,
            "GB": st.column_config.TextColumn("GB", help="Games behind the last playoff spot"),
        },
    )
    st.caption("Ties are broken by points for, then points against (higher wins), as in "
               "Sleeper. Commissioners can override seeding before the playoffs.")

caption = "Sorted by wins, then points for, then points against."
if data.median_game:
    caption = ("This league plays an extra game against the weekly median; "
               "sorted by total wins, then points for, then points against.")
st.caption(caption)

st.subheader("Points for vs. points against")
avg_pf, avg_pa = table.PF.mean(), table.PA.mean()
fig = go.Figure(go.Scatter(
    x=table.PF, y=table.PA, mode="markers+text", text=table.team,
    textposition="top center", textfont=dict(color=theme.INK_2, size=12),
    marker=dict(size=12, color=theme.HIGHLIGHT, line=dict(color=theme.SURFACE, width=2)),
    hovertemplate="<b>%{text}</b><br>PF %{x:.2f}<br>PA %{y:.2f}<extra></extra>",
))
fig.add_vline(avg_pf, line=dict(color=theme.AXIS, dash="dot", width=1))
fig.add_hline(avg_pa, line=dict(color=theme.AXIS, dash="dot", width=1))
fig.update_layout(height=480, xaxis_title="Points for", yaxis_title="Points against")
st.plotly_chart(fig, width="stretch")
st.caption("Right = scores a lot. Up = opponents score a lot against you (unlucky). "
           "Dotted lines are league averages.")

# -- Points vs. projected points ---------------------------------------------------------
st.subheader("Points vs. projected points")
proj = projections.team_projections(data)
if proj.empty:
    st.info("Sleeper projections are unavailable right now.")
    st.stop()

vs = proj.groupby("roster_id").agg(
    proj=("proj", "sum"), pf=("points", "sum"), diff=("diff", "sum"),
    per_week=("diff", "mean"), beat=("diff", lambda d: int((d > 0).sum())),
    weeks=("diff", "size"),
).reset_index()
vs["team"] = vs.roster_id.map(data.names)
vs["Beat"] = vs.beat.astype(str) + " of " + vs.weeks.astype(str)
vs = vs.sort_values("diff", ascending=False).reset_index(drop=True)
GOOD, BAD = theme.DIVERGING[-1][1], theme.DIVERGING[0][1]

left, right = st.columns([3, 2])
with left:
    fig = go.Figure(go.Bar(
        x=vs["diff"], y=vs.team, orientation="h",
        marker_color=[GOOD if d >= 0 else BAD for d in vs["diff"]],
        text=[f"{d:+.1f}" for d in vs["diff"]], textposition="outside",
        textfont=dict(color=theme.INK_2), cliponaxis=False,
        customdata=vs[["pf", "proj", "Beat"]].to_numpy(),
        hovertemplate=("<b>%{y}</b><br>%{x:+.2f} vs. projection<br>Actual %{customdata[0]:.2f}"
                       " · projected %{customdata[1]:.2f}<br>Beat projection "
                       "%{customdata[2]} weeks<extra></extra>"),
    ))
    fig.add_vline(0, line=dict(color=theme.AXIS, width=1))
    fig.update_layout(height=max(320, 30 * len(vs) + 80), bargap=0.3,
                      xaxis_title="Actual − projected points (season)",
                      yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, width="stretch")
with right:
    st.dataframe(
        vs[["team", "pf", "proj", "diff", "per_week", "Beat"]],
        hide_index=True, width="stretch", height=35 * (len(vs) + 1) + 3,
        column_config={
            "team": "Team",
            "pf": st.column_config.NumberColumn("PF", format="%.2f"),
            "proj": st.column_config.NumberColumn(
                "Proj PF", format="%.2f",
                help="Sleeper's projection for the lineup that was actually started"),
            "diff": st.column_config.NumberColumn("+/−", format="%+.2f",
                                                  help="Actual − projected, season"),
            "per_week": st.column_config.NumberColumn("+/− per week", format="%+.2f"),
            "Beat": st.column_config.TextColumn(
                "Beat proj", help="Weeks the team scored more than projected"),
        },
    )

grid = proj.pivot_table(index="roster_id", columns="week", values="diff").reindex(vs.roster_id)
pf_grid = proj.pivot_table(index="roster_id", columns="week", values="points").reindex(
    index=grid.index, columns=grid.columns)
pj_grid = proj.pivot_table(index="roster_id", columns="week", values="proj").reindex(
    index=grid.index, columns=grid.columns)
lim = max(float(grid.abs().max().max()), 1.0)
fig = go.Figure(go.Heatmap(
    z=grid.to_numpy(), x=[f"W{w}" for w in grid.columns], y=vs.team,
    customdata=pd.concat([pf_grid, pj_grid], axis=1, keys=["pf", "pj"]).to_numpy()
    .reshape(len(grid), 2, -1).transpose(0, 2, 1),
    colorscale=theme.DIVERGING, zmid=0, zmin=-lim, zmax=lim, xgap=2, ygap=2,
    colorbar=dict(title="+/−", thickness=12),
    hovertemplate=("<b>%{y}</b> · %{x}<br>%{z:+.2f} vs. projection<br>"
                   "Actual %{customdata[0]:.2f} · projected %{customdata[1]:.2f}<extra></extra>"),
))
fig.update_layout(height=max(300, 30 * len(vs) + 100), yaxis=dict(autorange="reversed"),
                  title="Actual − projected, by week")
st.plotly_chart(fig, width="stretch")
st.caption("Projected points = Sleeper's projection (this league's scoring) for each team's "
           "actual starting lineup that week; starters without a projection count as 0. "
           "Blue: outscored the projection. Red: fell short. Completed regular-season "
           "weeks only.")
