# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Streamlit dashboard for one Sleeper fantasy football league: standings, weekly scores, team pages, player stats, projections and "bye luck". All data comes from public, keyless sources (Sleeper API, nflverse CSV on GitHub). See README.md for user-facing setup and deployment to Streamlit Community Cloud.

## Commands

```
uv sync                          # install deps (.venv)
uv run streamlit run app.py      # run the app on http://localhost:8501
```

The app needs a league ID: `LEAGUE_ID` in `.streamlit/secrets.toml` (gitignored), the `LEAGUE_ID` env var, or `?league=<id>` in the URL. Optional secrets: `PRIVATE_PASSWORD`, `FANTASYPROS_API_KEY`.

There are no tests, linter config or build step. `main.py` is empty and unused. To verify a change, run the app against a real league.

Dependencies are declared twice: `pyproject.toml` (+ `uv.lock`) for local use, and `requirements.txt`, which Streamlit Cloud installs. Keep them in sync.

## Architecture

**Data flow:** `app.py` → `model.load_league(league_id)` → one `LeagueData` dataclass → stored in `st.session_state["data"]` → each page in `views/` reads it from there and calls pure functions in `sleeper/stats.py` / `sleeper/projections.py`.

- `app.py` is the entry point and router: resolves the league ID, loads data, renders the sidebar (refresh button, private unlock), and runs `st.navigation` over `views/*.py`. View files are scripts executed top to bottom, not modules with functions. The folder is called `views/` on purpose: `pages/` would trigger Streamlit's legacy multipage behavior.
- `sleeper/api.py` holds every HTTP call. Each is wrapped in `@st.cache_data` (15 min for league data, 1 h for stats/projections, 3 h for FantasyPros, 24 h for the ~5 MB player database, which Sleeper asks not to refetch often). Multi-week fetches run in a `ThreadPoolExecutor`. Cached functions take tuples (hashable) for week/stat lists. If you add a cached API function, also add it to the "Refresh data" clear list in `app.py`.
- `sleeper/model.py` turns raw JSON into DataFrames: `teams`, `team_weeks` (incl. median, W/L/T result, `final`/`regular` flags), `player_weeks` (rostered players' matchup points), `schedule` (pairings incl. future weeks), plus `player_stats`: every NFL player's weekly stats re-scored with the league's own `scoring_settings`.
- `sleeper/stats.py`: standings (Sleeper tiebreakers, optional median game, all-play, luck), playoff picture, optimal lineup via slot eligibility (`SLOT_ELIGIBILITY`), player values/summaries, waiver replacement levels and bye luck (best lineup with vs. without bye players, where both may use a replacement-level waiver pickup).
- `sleeper/schedule.py`: NFL byes and opponents from nflverse `games.csv`, with team abbreviations mapped to Sleeper's and a hardcoded `FALLBACK_BYES` if the download fails.
- `sleeper/player_view.py`: shared player popup used by the Players and Teams pages. Clickable tables use `table_key()`, which rotates the widget key so a stale selection is cleared after the popup closes.
- `sleeper/theme.py`: registers the `ffdash` plotly template on import (`app.py` imports it for that side effect), and provides `shade()` for pastel per-column gradients on Styler tables. Colors match `.streamlit/config.toml`.
- `sleeper/statcols.py`: which Sleeper stat keys to display per position, their labels and direction.
- `sleeper/bracket.py`: renders the playoff bracket as SVG.

## Conventions and gotchas

- **Week semantics:** `current_week` is the first week that is not final (99 = season over, 1 = preseason). Weeks `< current_week` are final; `last_regular_week = playoff_week_start - 1`. Many computations filter on `team_weeks.final & team_weeks.regular`.
- **Undocumented endpoints degrade gracefully:** `/stats/nfl/regular/...` and `/projections/nfl/regular/...` are undocumented. Callers catch failures and return empty frames, and the UI falls back to matchup points (`data.has_nfl_stats`). FantasyPros returns `{}` on any error. Keep this behavior: a failing optional source must never break a page.
- **Projection calibration:** Sleeper's projections overstate some event stats (first downs ~2.4×, 40+ yard plays ~3.5×). `projections.calibration()` rescales every projected stat by actual ÷ projected over all players in the completed weeks. Always pass those factors to `_league_points`, or projections run high in leagues that score those stats.
- **Divisions page** is only registered in `app.py` when the league has divisions.
- **Points:** matchup points use `custom_points` when set (commissioner overrides), else `points`.
- **Private view:** FantasyPros data is shown only when `private.is_unlocked()` (password from secrets, compared with `hmac.compare_digest`, unlocked per browser session). Never render FantasyPros data or its key outside that check. The FantasyPros API terms require crediting FantasyPros wherever its data appears.
- **FantasyPros → Sleeper matching** is by normalized name + position (team breaks ties), with team-abbreviation aliases. DEF players are keyed by team abbreviation in Sleeper's player DB.
