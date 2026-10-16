"""NFL stat columns shown on the Players page (keys as in Sleeper's weekly stats)."""

LABELS = {
    "pass_cmp": "Cmp", "pass_att": "Pass att", "pass_yd": "Pass yd", "pass_td": "Pass TD",
    "pass_int": "Int", "pass_sack": "Sacked",
    "rush_att": "Rush att", "rush_yd": "Rush yd", "rush_td": "Rush TD",
    "rec_tgt": "Targets", "rec": "Rec", "rec_yd": "Rec yd", "rec_td": "Rec TD",
    "fum_lost": "Fum lost",
    "fgm": "FG made", "fga": "FG att", "fgm_lng": "FG long", "xpm": "XP made", "xpa": "XP att",
    "sack": "Sacks", "int": "Def int", "fum_rec": "Fum rec", "td": "Def TD",
    "pts_allow": "Pts allowed", "yds_allow": "Yds allowed",
}

# Extra stats a league may score; shown in a player's weekly detail when he has any
SCORED_LABELS = {
    "pass_fd": "Pass 1st downs", "pass_cmp_40p": "Cmp 40+", "pass_2pt": "Pass 2pt",
    "pass_int_td": "Pick-six thrown",
    "rush_fd": "Rush 1st downs", "rush_40p": "Rush 40+", "rush_2pt": "Rush 2pt",
    "rec_fd": "Rec 1st downs", "rec_40p": "Rec 40+", "rec_2pt": "Rec 2pt",
    "bonus_rec_te": "TE rec bonus", "bonus_rec_rb": "RB rec bonus", "bonus_rec_wr": "WR rec bonus",
    "bonus_rush_yd_100": "100+ rush yd", "bonus_rec_yd_100": "100+ rec yd",
    "bonus_pass_yd_300": "300+ pass yd",
    "fgmiss": "FG missed", "fgm_yds_over_30": "FG yds over 30", "xpmiss": "XP missed",
    "fgm_50p": "FG 50+",
    "ff": "Forced fum", "safe": "Safeties", "blk_kick": "Blocked kicks", "def_td": "Def TD",
    "fum_rec_td": "Fum return TD", "st_td": "ST TD", "def_st_td": "Def ST TD",
    "st_ff": "ST forced fum", "st_fum_rec": "ST fum rec", "def_st_ff": "Def ST forced fum",
    "def_st_fum_rec": "Def ST fum rec",
    "pts_allow_0": "Allowed 0", "pts_allow_1_6": "Allowed 1-6", "pts_allow_7_13": "Allowed 7-13",
    "pts_allow_14_20": "Allowed 14-20", "pts_allow_21_27": "Allowed 21-27",
    "pts_allow_28_34": "Allowed 28-34", "pts_allow_35p": "Allowed 35+",
}


def label(key: str) -> str:
    return LABELS.get(key) or SCORED_LABELS.get(key) or key.replace("_", " ").capitalize()


BY_POSITION = {
    "QB": ["pass_cmp", "pass_att", "pass_yd", "pass_td", "pass_int", "pass_cmp_40p", "pass_sack",
           "rush_att", "rush_yd", "rush_td", "rush_40p", "fum_lost"],
    "RB": ["rush_att", "rush_yd", "rush_td", "rush_40p", "rec_tgt", "rec", "rec_yd", "rec_td", "rec_fd",
           "rec_40p", "fum_lost"],
    "WR": ["rec_tgt", "rec", "rec_yd", "rec_td", "rec_fd", "rec_40p", "rush_att", "rush_yd",
           "rush_td", "rush_40p", "fum_lost"],
    "TE": ["rec_tgt", "rec", "rec_yd", "rec_td", "rec_fd", "rec_40p", "fum_lost"],
    "K": ["fgm", "fga", "fgm_lng", "xpm", "xpa"],
    "DEF": ["sack", "int", "fum_rec", "td", "pts_allow", "yds_allow"],
}
# Shown when several (or all) positions are listed together
MIXED = ["pass_yd", "pass_td", "pass_int", "pass_cmp_40p", "rush_att", "rush_yd", "rush_td",
         "rush_40p", "rec_tgt", "rec", "rec_yd", "rec_td", "rec_fd", "rec_40p", "fum_lost"]

# How a stat adds up over a season (everything else is summed)
SEASON_MAX = {"fgm_lng"}
ALWAYS_PER_GAME = {"pts_allow", "yds_allow"}  # totals aren't meaningful for these

ALL = sorted({k for keys in [*BY_POSITION.values(), MIXED] for k in keys})


def columns_for(positions: list[str]) -> list[str]:
    if len(positions) == 1 and positions[0] in BY_POSITION:
        return BY_POSITION[positions[0]]
    return MIXED
