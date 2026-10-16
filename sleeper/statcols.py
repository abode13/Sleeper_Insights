"""NFL stat columns shown on the Players page (keys as in Sleeper's weekly stats)."""

LABELS = {
    "pass_cmp": "Cmp", "pass_att": "Pass att", "pass_yd": "Pass yd", "pass_td": "Pass TD",
    "pass_int": "Int thrown", "pass_sack": "Sacked",
    "rush_att": "Rush att", "rush_yd": "Rush yd", "rush_td": "Rush TD",
    "rec_tgt": "Targets", "rec": "Rec", "rec_yd": "Rec yd", "rec_td": "Rec TD",
    "fum_lost": "Fum lost",
    "fgm": "FG made", "fga": "FG att", "fgm_lng": "FG long", "xpm": "XP made", "xpa": "XP att",
    "sack": "Sacks", "int": "Def int", "fum_rec": "Fum rec", "td": "Def TD",
    "pts_allow": "Pts allowed", "yds_allow": "Yds allowed",
}

BY_POSITION = {
    "QB": ["pass_cmp", "pass_att", "pass_yd", "pass_td", "pass_int", "pass_sack",
           "rush_att", "rush_yd", "rush_td", "fum_lost"],
    "RB": ["rush_att", "rush_yd", "rush_td", "rec_tgt", "rec", "rec_yd", "rec_td", "fum_lost"],
    "WR": ["rec_tgt", "rec", "rec_yd", "rec_td", "rush_att", "rush_yd", "rush_td", "fum_lost"],
    "TE": ["rec_tgt", "rec", "rec_yd", "rec_td", "fum_lost"],
    "K": ["fgm", "fga", "fgm_lng", "xpm", "xpa"],
    "DEF": ["sack", "int", "fum_rec", "td", "pts_allow", "yds_allow"],
}
# Shown when several (or all) positions are listed together
MIXED = ["pass_yd", "pass_td", "pass_int", "rush_att", "rush_yd", "rush_td",
         "rec_tgt", "rec", "rec_yd", "rec_td"]

# How a stat adds up over a season (everything else is summed)
SEASON_MAX = {"fgm_lng"}
ALWAYS_PER_GAME = {"pts_allow", "yds_allow"}  # totals aren't meaningful for these

ALL = sorted({k for keys in BY_POSITION.values() for k in keys})


def columns_for(positions: list[str]) -> list[str]:
    if len(positions) == 1 and positions[0] in BY_POSITION:
        return BY_POSITION[positions[0]]
    return MIXED
