import plotly.graph_objects as go
import streamlit as st

from sleeper import statcols, stats, theme

data = st.session_state["data"]
st.title("Players")
if data.has_nfl_stats:
    st.caption("**Total** and **started** count points scored while on a roster in this "
               "league. **Games** and **Avg** cover every NFL game the player played this "
               "season, scored with this league's settings.")
else:
    st.caption("Only points scored while on a fantasy roster in this league are counted; "
               "weeks with 0 points are treated as missed games (NFL stats unavailable).")

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
view = view[view.games >= min_games].reset_index(drop=True)

cols = ["name", "pos", "nfl_team", "fantasy_team", "total", "games", "avg", "started",
        "started_pts"]
column_config = {
    "name": "Player", "pos": "Pos", "nfl_team": "NFL", "fantasy_team": "Fantasy team",
    "total": st.column_config.NumberColumn("Total", format="%.2f",
                                           help="Points while on a roster in this league"),
    "games": st.column_config.NumberColumn(
        "Games", help="NFL games played this season" if data.has_nfl_stats
        else "Weeks with non-zero points on a league roster"),
    "avg": st.column_config.NumberColumn("Avg", format="%.2f", help="Points per game played"),
    "started": "Started",
    "started_pts": st.column_config.NumberColumn("Pts as starter", format="%.2f"),
}

if data.has_nfl_stats:
    o1, o2 = st.columns([1, 3], vertical_alignment="center")
    show_stats = o1.toggle("Show NFL stats", value=True)
    per_game = o2.segmented_control("Stats as", ["Season totals", "Per game"],
                                    default="Season totals") == "Per game"
    if show_stats:
        keys = statcols.columns_for(pos)
        season = stats.player_season_stats(data, keys, per_game)
        view = view.join(season, on="player_id")
        cols += keys
        for k in keys:
            whole = (k in statcols.SEASON_MAX
                     or not (per_game or k in statcols.ALWAYS_PER_GAME))
            label = statcols.LABELS[k] + ("/g" if k in statcols.ALWAYS_PER_GAME else "")
            column_config[k] = st.column_config.NumberColumn(
                label, format="%d" if whole else "%.1f")
        if len(pos) != 1:
            st.caption("Pick a single position above for its full set of stats "
                       "(e.g. kicking or defense).")

event = st.dataframe(
    view[cols], hide_index=True, width="stretch", height=420, column_config=column_config,
    # Cell selection too, so clicking anywhere in a row picks that player
    on_select="rerun", selection_mode=["single-row", "single-cell"], key="players_table",
)
st.caption("👆 Click a player to see his week-by-week stats.")

# -- Player detail ------------------------------------------------------------------------
sel = event.selection if event else None
row = sel.rows[0] if sel and sel.rows else (sel.cells[0][0] if sel and sel.cells else None)
if row is not None and row < len(view):
    p = view.iloc[row]
    detail = stats.player_weekly_detail(data, p.player_id)
    nfl_team = p.nfl_team if isinstance(p.nfl_team, str) else "no NFL team"
    st.subheader(f"{p['name']} · {p.pos} · {nfl_team}", anchor="player-detail")
    if st.session_state.get("players_scrolled_to") != p.player_id:
        # Scroll down to the detail once per newly picked player
        st.session_state["players_scrolled_to"] = p.player_id
        st.iframe(
            "<script>setTimeout(() => window.parent.document.getElementById("
            "'player-detail')?.scrollIntoView({behavior: 'smooth', block: 'start'}), 300)"
            f"</script><!-- {p.player_id} -->",
            height=1,
        )
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Games played", int(p.games))
    m2.metric("Points per game", f"{p.avg:.2f}" if p.avg == p.avg else "–")
    m3.metric("Fantasy team now", p.fantasy_team)
    m4.metric("Points on league rosters", f"{p.total:.1f}")

    played = detail[detail.points.notna()]
    fig = go.Figure(go.Bar(
        x=played.week, y=played.points, marker_color=theme.HIGHLIGHT,
        hovertemplate="Week %{x}: %{y:.2f} pts<extra></extra>",
    ))
    fig.update_layout(height=260, xaxis=dict(title="Week", dtick=1), yaxis_title="Points",
                      bargap=0.35, margin=dict(t=20))
    st.plotly_chart(fig, width="stretch")

    keys = [k for k in statcols.BY_POSITION.get(p.pos, statcols.MIXED) if k in detail]
    show = ["week", "note", "fantasy_team", "started", "points"] + keys
    st.dataframe(
        detail[show], hide_index=True, width="stretch",
        column_config={
            "week": "Week", "note": "", "fantasy_team": "Fantasy team",
            "started": st.column_config.CheckboxColumn("Started"),
            "points": st.column_config.NumberColumn("Points", format="%.2f"),
            **{k: st.column_config.NumberColumn(statcols.LABELS[k], format="%d")
               for k in keys},
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