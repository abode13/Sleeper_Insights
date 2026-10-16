"""Playoff bracket drawn as inline SVG."""

from html import escape

from sleeper import theme

BOX_W, ROW_H, COL_GAP, SLOT_H, HEADER_H = 200, 30, 44, 74, 44
DIVISION_LEADER_FILL = theme.HIGHLIGHT
WILDCARD_FILL = theme.MUTED


def seed_order(size: int) -> list[int]:
    """Standard bracket order, e.g. 8 -> [1, 8, 4, 5, 2, 7, 3, 6]."""
    order = [1]
    while len(order) < size:
        n = len(order) * 2
        order = [x for s in order for x in (s, n + 1 - s)]
    return order


def round_names(rounds: int) -> list[str]:
    names = {1: "Final", 2: "Semifinals", 3: "Quarterfinals"}
    return [names.get(rounds - r, f"Round {r + 1}") for r in range(rounds)]


def round_weeks(first_week: int, rounds: int, round_type: int) -> list[str]:
    labels, week = [], first_week
    for r in range(rounds):
        span = 2 if round_type == 2 or (round_type == 1 and r == rounds - 1) else 1
        labels.append(f"Week {week}" if span == 1 else f"Weeks {week}–{week + span - 1}")
        week += span
    return labels


def bracket_height(n: int) -> int:
    size = 1
    while size < n:
        size *= 2
    return HEADER_H + (size // 2) * SLOT_H


def bracket_svg(teams: dict[int, dict], n: int, first_week: int, round_type: int = 0) -> str:
    """teams: seed -> {"team", "record", "avatar", "leader"}; n: number of playoff teams."""
    size = 1
    while size < n:
        size *= 2
    rounds = max(size.bit_length() - 1, 1)
    order = seed_order(size)

    # Each match is (top, bottom) where a side is a seed (int), a placeholder (str) or None (bye)
    matches = [[(order[i], order[i + 1] if order[i + 1] <= n else None)
                for i in range(0, size, 2)]]
    for r in range(1, rounds):
        prev, cur = matches[-1], []
        for i in range(0, len(prev), 2):
            cur.append((_advance(prev[i]), _advance(prev[i + 1])))
        matches.append(cur)

    width = (rounds + 1) * (BOX_W + COL_GAP)
    height = HEADER_H + (size // 2) * SLOT_H
    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" '
           f'style="max-width:{width}px;font-family:{escape(theme.FONT)}" '
           f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Playoff bracket">']

    names = round_names(rounds) + ["Champion"]
    weeks = round_weeks(first_week, rounds, round_type) + [""]
    for r in range(rounds + 1):
        x = r * (BOX_W + COL_GAP)
        out.append(f'<text x="{x}" y="16" font-size="14" font-weight="600" '
                   f'fill="{theme.INK}">{names[r]}</text>')
        out.append(f'<text x="{x}" y="34" font-size="12" fill="{theme.MUTED}">{weeks[r]}</text>')

    centers = []
    for r, round_matches in enumerate(matches):
        slot = (size // 2) * SLOT_H / len(round_matches)
        x = r * (BOX_W + COL_GAP)
        cy_list = []
        for i, (top, bottom) in enumerate(round_matches):
            cy = HEADER_H + slot * (i + 0.5)
            cy_list.append(cy)
            if r == 0 and bottom is None:
                continue  # bye: the top seed appears directly in the next round
            y = cy - ROW_H
            out.append(f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{2 * ROW_H}" rx="6" '
                       f'fill="white" stroke="{theme.GRID}" stroke-width="1.5"/>')
            out.append(f'<line x1="{x}" y1="{cy}" x2="{x + BOX_W}" y2="{cy}" '
                       f'stroke="{theme.GRID}" stroke-width="1"/>')
            out.extend(_row(x, y, top, teams))
            out.extend(_row(x, cy, bottom, teams))
            if r > 0:  # connectors from the two feeding matches
                for child, py in ((2 * i, centers[r - 1][2 * i]),
                                  (2 * i + 1, centers[r - 1][2 * i + 1])):
                    if r == 1 and matches[0][child][1] is None:
                        continue
                    mid = x - COL_GAP / 2
                    ty = cy - ROW_H / 2 if child % 2 == 0 else cy + ROW_H / 2
                    out.append(f'<path d="M{x - COL_GAP} {py} H{mid} V{ty} H{x}" fill="none" '
                               f'stroke="{theme.AXIS}" stroke-width="1.5"/>')
        centers.append(cy_list)

    # Champion slot
    x, cy = rounds * (BOX_W + COL_GAP), centers[-1][0]
    out.append(f'<path d="M{x - COL_GAP} {cy} H{x}" stroke="{theme.AXIS}" stroke-width="1.5"/>')
    out.append(f'<rect x="{x}" y="{cy - ROW_H / 2}" width="{BOX_W}" height="{ROW_H}" rx="6" '
               f'fill="{theme.SURFACE}" stroke="{theme.AXIS}" stroke-width="1.5" '
               f'stroke-dasharray="4 3"/>')
    out.append(f'<text x="{x + 12}" y="{cy + 5}" font-size="13" fill="{theme.INK_2}">'
               f'🏆 Champion</text>')
    out.append("</svg>")
    return "".join(out)


def _advance(match):
    """What moves on from a match: the top seed on a bye, otherwise a placeholder."""
    top, bottom = match
    if bottom is None:
        return top
    if isinstance(top, int) and isinstance(bottom, int):
        return f"Winner #{min(top, bottom)} / #{max(top, bottom)}"
    return "Winner of semifinal" if "semi" not in str(top) else "Winner"


def _row(x, y, side, teams):
    cy = y + ROW_H / 2
    if not isinstance(side, int):
        return [f'<text x="{x + 12}" y="{cy + 4}" font-size="12" font-style="italic" '
                f'fill="{theme.MUTED}">{escape(str(side or ""))}</text>']
    t = teams.get(side, {})
    fill = DIVISION_LEADER_FILL if t.get("leader") else WILDCARD_FILL
    parts = [
        f'<circle cx="{x + 16}" cy="{cy}" r="10" fill="{fill}"/>',
        f'<text x="{x + 16}" y="{cy + 4}" font-size="11" font-weight="700" fill="white" '
        f'text-anchor="middle">{side}</text>',
    ]
    name_x = x + 32
    if t.get("avatar"):
        parts.append(f'<image href="{escape(t["avatar"])}" x="{name_x}" y="{cy - 10}" '
                     f'width="20" height="20" preserveAspectRatio="xMidYMid slice"/>')
        name_x += 26
    name = t.get("team", f"Seed {side}")
    if len(name) > 16:
        name = name[:15] + "…"
    parts.append(f'<text x="{name_x}" y="{cy + 4}" font-size="13" fill="{theme.INK}">'
                 f'{escape(name)}</text>')
    parts.append(f'<text x="{x + BOX_W - 10}" y="{cy + 4}" font-size="12" fill="{theme.MUTED}" '
                 f'text-anchor="end">{escape(t.get("record", ""))}</text>')
    return parts
