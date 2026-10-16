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

cols = ["Rank"] + (["avatar"] if table.avatar.notna().any() else []) + ["team", "owner", "Record", "Median"]
if data.median_game:
    table["Total"] = table["Tot W"].astype(str) + "-" + table["Tot L"].astype(str)
    cols.append("Total")
cols += ["PF", "PA", "Avg PF", "All-play", "AP %", "Luck", "Bye luck"]

st.dataframe(
    table[cols],
    hide_index=True,
    width="stretch",
    height=35 * (len(table) + 1) + 3,
    column_config={
        "avatar": st.column_config.ImageColumn("", width="small"),
        "team": "Team",
        "owner": "Manager",
        "Median": st.column_config.TextColumn(
            "Median", help="Record vs. the league median score each week"),
        "Total": st.column_config.TextColumn("Total", help="H2H + median games"),
        "PF": st.column_config.NumberColumn("PF", format="%.2f"),
        "PA": st.column_config.NumberColumn("PA", format="%.2f"),
        "Avg PF": st.column_config.NumberColumn("Avg PF", format="%.2f"),
        "All-play": st.column_config.TextColumn(
            "All-play", help="Record if you had played every team every week"),
        "AP %": st.column_config.ProgressColumn("All-play %", format="percent",
                                                min_value=0, max_value=1),
        "Luck": st.column_config.NumberColumn(
            "Luck", format="%+.1f",
            help="Actual H2H wins − expected wins from the all-play record"),
        "Bye luck": st.column_config.NumberColumn(
            "Bye luck", format="%+.1f",
            help="Points opponents lost to byes − points you lost to byes (played weeks). "
                 "See the Bye luck page."),
    },
)
if data.median_game:
    st.caption("This league plays an extra game against the weekly median; "
               "standings are sorted by total wins, then points for.")

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
