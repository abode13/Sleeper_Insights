# Sleeper League Dashboard

A Streamlit dashboard for a Sleeper fantasy football league. It shows standings (H2H, median and all-play records, luck), weekly scores, team pages, player stats and **bye luck**: the points that you and your opponents lost to NFL byes, for the weeks played and for the rest of the season.

Data comes from the public [Sleeper API](https://docs.sleeper.com/) and NFL bye weeks from [nflverse](https://github.com/nflverse/nfldata). Neither needs a login or API key.

## Run locally

```
uv sync
```

Put your league ID (the number in the sleeper.com league URL) in `.streamlit/secrets.toml`:

```toml
LEAGUE_ID = "123456789012345678"
```

```
uv run streamlit run app.py
```

Without a configured ID, the app asks for one, or you can open it with `?league=<id>`.

## Share with the league (Streamlit Community Cloud)

1. Push this folder to a GitHub repo. `secrets.toml` is gitignored, so it won't be pushed.
2. On https://share.streamlit.io, click **Create app**, pick the repo, and set the main file to `app.py`.
3. Under **Advanced settings**, pick Python 3.12 or 3.13 and paste `LEAGUE_ID = "…"` into **Secrets**.
4. Share the app URL. Under the app's sharing settings you can make it public or invite-only.

## Private projections (owner only)

Projections and rankings appear only after unlocking with a password, so league mates don't see them. Add these to `.streamlit/secrets.toml` and to the Streamlit Cloud **Secrets**:

```toml
PRIVATE_PASSWORD = "choose-a-password"
FANTASYPROS_API_KEY = "…"   # optional, see below
```

- Unlock: **🔒 Private** in the sidebar → password. It stays unlocked for that browser session; **Lock private view** hides it again.
- **Sleeper projections** (this week and rest of season, scored with the league's rules) work without a key.
- **FantasyPros** expert consensus rankings and projections need a free personal API key. Request one via FantasyPros support ("How do I request access to the FantasyPros API?"). The data is for personal, non-commercial use and must credit FantasyPros, which the app does.

## Layout

- `sleeper/api.py`: Sleeper API calls (cached for 15 min; the player database for 24 h)
- `sleeper/schedule.py`: NFL bye weeks from the nflverse schedule
- `sleeper/model.py`: builds the DataFrames (teams, team-weeks, player-weeks, schedule)
- `sleeper/stats.py`: standings, all-play, best possible lineup, player stats, bye luck
- `sleeper/private.py`, `sleeper/projections.py`: password unlock; Sleeper and FantasyPros projections
- `views/`: one file per dashboard page (not named `pages/`, which Streamlit would treat as its legacy page list)
