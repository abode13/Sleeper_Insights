"""Shared chart styling (validated reference palette, light mode)."""

import plotly.graph_objects as go
import plotly.io as pio

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
HIGHLIGHT = SERIES[0]
CONTEXT = "#c3c2b7"  # de-emphasised marks (the "rest of the league")

SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
# Diverging: red (bad) <- gray midpoint -> blue (good)
DIVERGING = [
    [0.0, "#b52f2f"], [0.25, "#e88a89"], [0.5, "#f0efec"], [0.75, "#86b6ef"], [1.0, "#1c5cab"]
]

FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

# Pastel table shading: worst value in a column = red, then orange, yellow, best = green
_TINT_STOPS = [(0.0, (246, 196, 196)), (0.33, (250, 216, 186)), (0.66, (249, 238, 184)),
               (1.0, (200, 230, 196))]


def _tint(t: float) -> tuple[int, int, int]:
    for (t0, c0), (t1, c1) in zip(_TINT_STOPS, _TINT_STOPS[1:]):
        if t <= t1:
            f = (t - t0) / (t1 - t0)
            return tuple(round(a + (b - a) * f) for a, b in zip(c0, c1))
    return _TINT_STOPS[-1][1]


def gradient_css(values, reverse: bool = False) -> list[str]:
    """CSS backgrounds for one table column: its min is red, its max green (or reversed)."""
    import pandas as pd

    v = pd.to_numeric(pd.Series(values), errors="coerce")
    lo, hi = v.min(), v.max()
    if pd.isna(lo) or hi == lo:
        return [""] * len(v)
    out = []
    for x in v:
        if pd.isna(x):
            out.append("")
            continue
        t = (x - lo) / (hi - lo)
        r, g, b = _tint(1 - t if reverse else t)
        out.append(f"background-color: rgb({r}, {g}, {b})")
    return out


def shade(df, columns, values=None, lower_is_better=(), relevant=None):
    """Styler for `df` with a pastel per-column gradient on `columns`.

    `values` supplies the numbers to scale by when `df` holds pre-formatted text;
    columns in `lower_is_better` get the reversed scale (low = green). `relevant`
    (column -> boolean Series) limits shading and scaling to the rows where that
    stat makes sense, e.g. pass yards only for QBs.
    """
    values = df if values is None else values
    flip = set(lower_is_better)
    relevant = relevant or {}

    def column_css(col):
        v = values[col.name]
        if col.name in relevant:
            v = v.where(relevant[col.name])
        return gradient_css(v, col.name in flip)

    return df.style.apply(column_css, subset=list(columns))

pio.templates["ffdash"] = go.layout.Template(
    layout=dict(
        font=dict(family=FONT, color=INK_2, size=13),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        colorway=SERIES,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(gridcolor=GRID, linecolor=AXIS, zerolinecolor=AXIS, tickcolor=AXIS,
                   tickfont=dict(color=MUTED), title_font=dict(color=INK_2)),
        yaxis=dict(gridcolor=GRID, linecolor=AXIS, zerolinecolor=AXIS, tickcolor=AXIS,
                   tickfont=dict(color=MUTED), title_font=dict(color=INK_2)),
        hoverlabel=dict(bgcolor="white", bordercolor=GRID, font=dict(family=FONT, color=INK)),
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, title_text=""),
        title=dict(font=dict(color=INK, size=15)),
    )
)
pio.templates.default = "plotly+ffdash"