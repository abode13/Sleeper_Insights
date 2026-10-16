import plotly.graph_objects as go
import streamlit as st

from sleeper import player_view, private, projections, statcols, stats, theme

data = st.session_state["data"]
st.title("Players")
if data.has_nfl_stats:
    st.caption("**Total**, **Games** and **Avg** cover every NFL game the player played this "
               "season, scored with this league's settings. **Started** counts starts in this "
               "league. Sorted by Avg; click a header to sort by something else.")
else:
    st.caption("Only points scored while on a fantasy roster in this league are counted; "
               "weeks with 0 points are treated as missed games (NFL stats unavailable).")

o1, o2, o3 = st.columns([1, 1, 2], vertical_alignment="center")
include_fa = o1.toggle(
    "Include free agents", value=False, disabled=not data.has_nfl_stats,
    help="Also list every NFL player nobody in this league has rostered this season — "
         "handy for finding waiver pickups" if data.has_nfl_stats
    else "Needs NFL player stats, which are unavailable right now")
show_stats = o2.toggle("Show NFL stats", value=True, disabled=not data.has_nfl_stats)
per_game = o3.segmented_control("Stats as", ["Season totals", "Per game"],
                                default="Season totals",
                                disabled=not data.has_nfl_stats) == "Per game"

summary = stats.player_summary(data, include_free_agents=include_fa)
if summary.empty:
    st.info("No completed weeks yet.")
    st.stop()

f0, f1, f2, f3, f4 = st.columns([2, 2, 2, 3, 1])
search = f0.text_input("Search", placeholder="Player name…")
positions = sorted(summary.pos.dropna().unique())
pos = f1.multiselect("Position", positions, placeholder="All positions")
nfl_teams = sorted(summary.nfl_team.dropna().unique())
nfl = f2.multiselect("NFL team", nfl_teams, placeholder="All NFL teams")
teams = sorted(summary.fantasy_team.unique())
team = f3.multiselect("Fantasy team", teams, placeholder="All teams")
min_games = f4.number_input("Min games", 0, 18, 1)

view = summary
if search.strip():
    view = view[view.name.str.contains(search.strip(), case=False, regex=False, na=False)]
if pos:
    view = view[view.pos.isin(pos)]
if nfl:
    view = view[view.nfl_team.isin(nfl)]
if team:
    view = view[view.fantasy_team.isin(team)]
view = view[view.games >= min_games].reset_index(drop=True)

cols = ["name", "pos", "nfl_team", "fantasy_team", "total", "games", "avg", "started",
        "started_pts"]
column_config = {
    # Pinned so names stay visible when scrolling right to the stat columns
    "name": st.column_config.TextColumn("Player", pinned=True),
    "pos": "Pos", "nfl_team": "NFL",
    "fantasy_team": st.column_config.TextColumn(
        "Fantasy team", help="Team that has him now (Free agent if nobody does). "
                             "Click the player to see who had him each week."),
    "total": st.column_config.NumberColumn(
        "Total", format="%.2f",
        help="Season points from every NFL game played (this league's scoring)"
        if data.has_nfl_stats else "Points while on a roster in this league"),
    "games": st.column_config.NumberColumn(
        "Games", help="NFL games played this season" if data.has_nfl_stats
        else "Weeks with non-zero points on a league roster"),
    "avg": st.column_config.NumberColumn("Avg", format="%.2f", help="Points per game played"),
    "started": "Started",
    "started_pts": st.column_config.NumberColumn("Pts as starter", format="%.2f"),
}

if data.has_nfl_stats:
    if show_stats:
        keys = statcols.columns_for(pos)
        season = stats.player_season_stats(data, keys, per_game)
        view = view.join(season, on="player_id")
        cols += keys
        for k in keys:
            whole = (k in statcols.SEASON_MAX
                     or not (per_game or k in statcols.ALWAYS_PER_GAME))
            label = statcols.label(k) + ("/g" if k in statcols.ALWAYS_PER_GAME else "")
            pts = data.scoring.get(k)
            column_config[k] = st.column_config.NumberColumn(
                label, format="%d" if whole else "%.1f",
                help=f"Scored in this league: {pts:+g} pts each" if pts else None)
        if len(pos) != 1:
            st.caption("Pick a single position above for its full set of stats "
                       "(e.g. kicking or defense).")

# -- Projections: Sleeper for everyone, FantasyPros only when unlocked --------------------
week = projections.projection_weeks(data)
extra = []
proj = projections.sleeper_projections(data)
if not proj.empty and week:
    view = view.merge(proj, on="player_id", how="left")
    # Players on bye this week are projected 0, not missing
    on_bye = view.nfl_team.map(data.byes) == week[0]
    view.loc[on_bye & view.proj_week.isna(), "proj_week"] = 0.0
    extra += ["proj_week", "proj_ros"]
    column_config["proj_week"] = st.column_config.NumberColumn(
        f"Proj W{week[0]}", format="%.1f",
        help="Sleeper projection for this week, in this league's scoring")
    column_config["proj_ros"] = st.column_config.NumberColumn(
        "Proj ROS", format="%.1f",
        help=f"Sleeper projection for the rest of the regular season "
             f"(weeks {week[0]}–{data.last_regular_week}), in this league's scoring")

if private.is_unlocked():
    fp, unmatched = projections.fantasypros(data, private.fantasypros_key())
    if not fp.empty:
        view = view.merge(fp, on="player_id", how="left")
        extra += ["fp_ecr", "fp_pos_rank", "fp_proj", "fp_ros_ecr", "fp_ros_pos_rank"]
        column_config["fp_ecr"] = st.column_config.NumberColumn(
            f"🔒 ECR W{week[0]}", format="%d",
            help="Private · FantasyPros expert consensus rank, this week (half PPR)")
        column_config["fp_pos_rank"] = st.column_config.TextColumn(
            f"🔒 Pos W{week[0]}", help="Private · FantasyPros position rank, this week")
        column_config["fp_proj"] = st.column_config.NumberColumn(
            f"🔒 FP W{week[0]}", format="%.1f",
            help="Private · FantasyPros projection, this week (half PPR)")
        column_config["fp_ros_ecr"] = st.column_config.NumberColumn(
            "🔒 ECR ROS", format="%d",
            help="Private · FantasyPros expert consensus rank, rest of season (half PPR)")
        column_config["fp_ros_pos_rank"] = st.column_config.TextColumn(
            "🔒 Pos ROS", help="Private · FantasyPros position rank, rest of season")
    if fp.empty:
        st.caption("🔒 FantasyPros: add `FANTASYPROS_API_KEY` to secrets to show ECR & "
                   "FantasyPros projections (only visible to you).")
    else:
        note = "🔒 columns are only visible to you. Rankings & projections: FantasyPros."
        if unmatched:
            note += f" {len(unmatched)} FantasyPros players couldn't be matched."
        st.caption(note)

i = cols.index("avg") + 1
cols[i:i] = extra

numeric_cols = [c for c in cols if c not in (
    "name", "pos", "nfl_team", "fantasy_team", "fp_pos_rank", "fp_ros_pos_rank")]
event = st.dataframe(
    theme.shade(view[cols], numeric_cols,
                lower_is_better=statcols.lower_is_better(numeric_cols, data.scoring)
                + ["fp_ecr", "fp_ros_ecr"],
                # Only shade stats that belong to the player's position (no red 0 pass
                # yards for running backs)
                relevant={k: view.pos.map(lambda p, k=k: k in statcols.BY_POSITION.get(
                    p, statcols.MIXED)) for k in numeric_cols if k in statcols.ALL}),
    hide_index=True, width="stretch",
    height=min(420, 35 * (len(view) + 1) + 3),
    column_config=column_config,
    # Cell selection (no row checkboxes): clicking anywhere in a row picks that player.
    # The key changes with the filters, so filtering clears a previous selection.
    on_select="rerun", selection_mode="single-cell",
    key=player_view.table_key("players", search, pos, nfl, team, min_games, include_fa),
)
st.caption("👆 Click a player to see his week-by-week stats.")

row = player_view.selected_row(event)
if row is not None and row < len(view):
    player_view.show_player(data, view.iloc[row].player_id)

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
fig.update_layout(height=max(160, 24 * len(labels) + 80), yaxis=dict(autorange="reversed"),
                  plot_bgcolor=theme.SURFACE)
st.plotly_chart(fig, width="stretch")
st.caption("Blank cells: not on a fantasy roster that week, or a bye.")