import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from sleeper import stats, theme

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
    by_seed = seeds.set_index("Seed")
    lines = []
    for a, b in pairs:
        if b is None:
            lines.append(f"- **#{a} {by_seed.loc[a, 'team']}** — first-round bye")
        else:
            lines.append(f"- #{a} {by_seed.loc[a, 'team']} vs. #{b} {by_seed.loc[b, 'team']}")
    st.markdown("\n".join(["**First round**"] + lines))
    rec_col = "Total" if data.median_game else "Record"
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
