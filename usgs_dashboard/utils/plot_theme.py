"""Plotly light/dark themes for the dashboard's figures.

Colors mirror the tokens in assets/theme.css (surface, line, fg, ...). The browser can't
share CSS variables with Plotly, so the values are repeated here; change both together.

Usage:
    from usgs_dashboard.utils import plot_theme
    plot_theme.apply_theme(fig, dark=bool(dark_mode))
"""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# Okabe-Ito colorblind-safe cycle, used only for traces that don't set their own color.
COLORWAY = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#56B4E9", "#CC79A7", "#F0E442", "#000000"]

_PALETTES = {
    "light": dict(
        surface="#FFFFFF", grid="#E3E9F0", line="#C9D4E0", fg="#14243A", fg_muted="#4A5C73",
        menu_bg="#EDF2F7", menu_border="#C9D4E0", menu_fg="#14243A", hover_bg="#FFFFFF",
        strong_line="#14243A",
    ),
    "dark": dict(
        surface="#142133", grid="#26384F", line="#3A4F69", fg="#E6EDF6", fg_muted="#A4B4C8",
        menu_bg="#DCE5EF", menu_border="#3A4F69", menu_fg="#14243A", hover_bg="#1B2B41",
        strong_line="#F2F6FB",
    ),
}

_FONT_FAMILY = "Fira Sans, system-ui, -apple-system, 'Segoe UI', sans-serif"


def _build_template(p: dict) -> go.layout.Template:
    axis = dict(gridcolor=p["grid"], linecolor=p["line"], zerolinecolor=p["grid"],
                tickcolor=p["line"], title=dict(font=dict(color=p["fg_muted"])))
    return go.layout.Template(layout=dict(
        paper_bgcolor=p["surface"],
        plot_bgcolor=p["surface"],
        font=dict(family=_FONT_FAMILY, size=12, color=p["fg"]),
        colorway=COLORWAY,
        margin=dict(l=56, r=16, t=40, b=48),
        xaxis=axis,
        yaxis=axis,
        hoverlabel=dict(bgcolor=p["hover_bg"], bordercolor=p["line"], font=dict(color=p["fg"])),
        legend=dict(font=dict(color=p["fg"])),
        updatemenudefaults=dict(bgcolor=p["menu_bg"], bordercolor=p["menu_border"],
                                font=dict(color=p["menu_fg"], size=11)),
    ))


for _name, _pal in _PALETTES.items():
    pio.templates[f"streamflow_{_name}"] = _build_template(_pal)


def template_name(dark: bool) -> str:
    return "streamflow_dark" if dark else "streamflow_light"


def apply_theme(fig: go.Figure, dark: bool) -> go.Figure:
    """Apply the light/dark template to `fig` in place and return it.

    Traces drawn in plain "black" (the observed line) are flipped to the theme's strong
    foreground so they stay visible on the dark surface, and any button menus take the
    theme's menu colors (explicit colors on them would otherwise override the template).

    Menu buttons stay light chips with dark text in BOTH themes: plotly.js paints the active
    and hovered button a fixed near-white (#F4FAFF), so light text on a dark menu would vanish.
    """
    pal = _PALETTES["dark" if dark else "light"]
    fig.update_layout(template=template_name(dark))
    if dark:
        for trace in fig.data:
            line = getattr(trace, "line", None)
            if line is not None and getattr(line, "color", None) == "black":
                line.color = pal["strong_line"]
    for menu in fig.layout.updatemenus:
        menu.update(bgcolor=pal["menu_bg"], bordercolor=pal["menu_border"],
                    font=dict(color=pal["menu_fg"], size=11))
    return fig
