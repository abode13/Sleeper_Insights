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

# Soft table shading: lowest value in a column = no tint, highest = light blue (step 150)
_TINT_LOW, _TINT_HIGH = (252, 252, 251), (183, 211, 246)


def gradient_css(values) -> list[str]:
    """CSS backgrounds for one table column, scaled from its min to its max."""
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
        r, g, b = (round(a + (c - a) * t) for a, c in zip(_TINT_LOW, _TINT_HIGH))
        out.append(f"background-color: rgb({r}, {g}, {b})")
    return out


def shade(df, columns, values=None):
    """Styler for `df` with a soft per-column gradient on `columns`.

    `values` supplies the numbers to scale by when `df` holds pre-formatted text.
    """
    values = df if values is None else values
    return df.style.apply(lambda col: gradient_css(values[col.name]), subset=list(columns))

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