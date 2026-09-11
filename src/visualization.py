"""
visualization.py
================
Phase 8 — Reusable Plotly Figure Factory for the Nassau Candy Dashboard.

Every function returns a fully configured ``plotly.graph_objects.Figure``
ready for ``st.plotly_chart()``. Consistent styling is applied via the
project's dark-mode colour palette.

Usage (as module):
    from src.visualization import (
        bar_chart, line_chart, pie_chart, scatter_chart,
        choropleth_map, scattergeo_map, heatmap, box_chart,
        route_leaderboard_chart, kpi_gauge,
    )

Author: Nassau Candy Analytics Team
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils import (
    FACTORY_COLOURS,
    PALETTE,
    REGION_COLOURS,
    SHIP_MODE_COLOURS,
    get_logger,
)

logger = get_logger(__name__)

QUALITATIVE_COLORS: List[str] = [
    "#6C63FF", "#43E97B", "#FF6584", "#F7B731", "#4FC3F7",
    "#A78BFA", "#38F9D7", "#FC5C7D", "#FCA652", "#29B6F6",
]

def _get_theme_config() -> Tuple[str, Dict, Dict, str]:
    """Dynamically determine Plotly template, font color, and grid styling based on active theme."""
    try:
        import streamlit as st
        active_theme = st.session_state.get("theme", "dark").lower()
    except Exception:
        active_theme = "dark"

    if active_theme == "light":
        template = "plotly_white"
        text_color = "#0F172A"
        muted_color = "#64748B"
        legend_bg = "rgba(255,255,255,0.85)"
        legend_border = "rgba(83,72,232,0.2)"
        grid_color = "rgba(100,116,139,0.12)"
    else:
        template = "plotly_dark"
        text_color = "#E8EAED"
        muted_color = "#9AA0B9"
        legend_bg = "rgba(30,33,48,0.75)"
        legend_border = "rgba(108,99,255,0.25)"
        grid_color = "rgba(154,160,185,0.15)"

    base_layout = dict(
        template=template,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Plus Jakarta Sans, Inter, sans-serif", size=12, color=text_color),
        margin=dict(l=40, r=20, t=60, b=40),
        legend=dict(
            bgcolor=legend_bg,
            bordercolor=legend_border,
            borderwidth=1,
            font=dict(size=11, color=text_color),
        ),
    )
    axis_style = dict(
        gridcolor=grid_color,
        linecolor="rgba(154,160,185,0.25)",
        zerolinecolor="rgba(154,160,185,0.25)",
        tickfont=dict(size=11, color=muted_color),
    )
    return template, base_layout, axis_style, text_color


def _apply_base(fig: go.Figure, title: str = "", height: int = 420) -> go.Figure:
    """Apply theme-adaptive layout to any Plotly figure."""
    _, base_layout, axis_style, text_color = _get_theme_config()
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=15, color=text_color, family="Plus Jakarta Sans, Inter, sans-serif"),
            x=0.01,
        ),
        height=height,
        **base_layout,
    )
    fig.update_xaxes(**axis_style)
    fig.update_yaxes(**axis_style)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# GENERIC CHARTS
# ─────────────────────────────────────────────────────────────────────────────

def bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: Optional[str] = None,
    title: str = "",
    orientation: str = "v",
    color_map: Optional[Dict[str, str]] = None,
    height: int = 420,
    barmode: str = "group",
) -> go.Figure:
    """
    Create a styled vertical or horizontal bar chart.

    Args:
        df:          Data source.
        x:           Column for x-axis.
        y:           Column for y-axis.
        color:       Optional column to colour bars by.
        title:       Chart title.
        orientation: ``"v"`` (vertical) or ``"h"`` (horizontal).
        color_map:   Custom colour mapping dict.
        height:      Figure height in pixels.
        barmode:     Plotly barmode (``"group"`` or ``"stack"``).

    Returns:
        Plotly Figure.
    """
    kwargs: Dict = dict(
        x=x, y=y, color=color, orientation=orientation, barmode=barmode,
        color_discrete_map=color_map or {},
        color_discrete_sequence=QUALITATIVE_COLORS,
    )
    fig = px.bar(df, **kwargs)
    fig.update_traces(marker_line_width=0, opacity=0.9)
    return _apply_base(fig, title=title, height=height)


def line_chart(
    df: pd.DataFrame,
    x: str,
    y: str | List[str],
    color: Optional[str] = None,
    title: str = "",
    markers: bool = True,
    height: int = 380,
) -> go.Figure:
    """
    Create a styled line chart.

    Args:
        df:      Data source.
        x:       Column for x-axis.
        y:       Column(s) for y-axis.
        color:   Optional column to colour lines by.
        title:   Chart title.
        markers: Whether to show point markers.
        height:  Figure height in pixels.

    Returns:
        Plotly Figure.
    """
    fig = px.line(
        df, x=x, y=y, color=color,
        markers=markers,
        color_discrete_sequence=QUALITATIVE_COLORS,
    )
    fig.update_traces(line_width=2.5)
    return _apply_base(fig, title=title, height=height)


def pie_chart(
    df: pd.DataFrame,
    names: str,
    values: str,
    title: str = "",
    color_map: Optional[Dict[str, str]] = None,
    height: int = 380,
    hole: float = 0.4,
) -> go.Figure:
    """
    Create a donut / pie chart.

    Args:
        df:        Data source.
        names:     Column for slice labels.
        values:    Column for slice sizes.
        title:     Chart title.
        color_map: Custom colour mapping.
        hole:      Hole size (0 = pie, > 0 = donut).
        height:    Figure height.

    Returns:
        Plotly Figure.
    """
    fig = px.pie(
        df, names=names, values=values,
        hole=hole,
        color=names,
        color_discrete_map=color_map or {},
        color_discrete_sequence=QUALITATIVE_COLORS,
    )
    fig.update_traces(
        textposition="outside",
        textinfo="percent+label",
        marker=dict(line=dict(color=PALETTE["background"], width=2)),
    )
    fig.update_layout(showlegend=True)
    return _apply_base(fig, title=title, height=height)


def scatter_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: Optional[str] = None,
    size: Optional[str] = None,
    hover_data: Optional[List[str]] = None,
    title: str = "",
    color_map: Optional[Dict[str, str]] = None,
    height: int = 420,
) -> go.Figure:
    """
    Create a styled scatter chart.

    Args:
        df:         Data source.
        x:          X-axis column.
        y:          Y-axis column.
        color:      Optional column to colour points.
        size:       Optional column to size points.
        hover_data: Extra columns shown on hover.
        title:      Chart title.
        color_map:  Custom colour mapping.
        height:     Figure height.

    Returns:
        Plotly Figure.
    """
    fig = px.scatter(
        df, x=x, y=y, color=color, size=size,
        hover_data=hover_data or [],
        color_discrete_map=color_map or {},
        color_discrete_sequence=QUALITATIVE_COLORS,
        opacity=0.8,
    )
    fig.update_traces(marker=dict(line=dict(width=0.5, color="rgba(0,0,0,0.4)")))
    return _apply_base(fig, title=title, height=height)


def box_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: Optional[str] = None,
    title: str = "",
    color_map: Optional[Dict[str, str]] = None,
    points: str = "outliers",
    height: int = 420,
) -> go.Figure:
    """
    Create a box / violin plot.

    Args:
        df:        Data source.
        x:         Categorical grouping column.
        y:         Numeric values column.
        color:     Optional colour column.
        title:     Chart title.
        color_map: Custom colour mapping.
        points:    ``"outliers"``, ``"all"``, or ``False``.
        height:    Figure height.

    Returns:
        Plotly Figure.
    """
    fig = px.box(
        df, x=x, y=y, color=color or x,
        points=points,
        color_discrete_map=color_map or {},
        color_discrete_sequence=QUALITATIVE_COLORS,
    )
    fig.update_traces(marker=dict(size=3, opacity=0.5))
    return _apply_base(fig, title=title, height=height)


def heatmap(
    df: pd.DataFrame,
    title: str = "",
    colorscale: str = "Viridis",
    height: int = 500,
    x_label: str = "",
    y_label: str = "",
) -> go.Figure:
    """
    Create a heatmap from a 2-D DataFrame (rows = y, columns = x).

    Args:
        df:         Pivot DataFrame (numeric values).
        title:      Chart title.
        colorscale: Plotly colorscale name.
        height:     Figure height.
        x_label:    X-axis label.
        y_label:    Y-axis label.

    Returns:
        Plotly Figure.
    """
    fig = go.Figure(
        data=go.Heatmap(
            z=df.values,
            x=df.columns.tolist(),
            y=df.index.tolist(),
            colorscale=colorscale,
            hoverongaps=False,
            colorbar=dict(
                tickfont=dict(color=PALETTE["muted"]),
                bgcolor="rgba(0,0,0,0)",
            ),
        )
    )
    fig.update_xaxes(title_text=x_label, **_AXIS_STYLE)
    fig.update_yaxes(title_text=y_label, **_AXIS_STYLE)
    return _apply_base(fig, title=title, height=height)


# ─────────────────────────────────────────────────────────────────────────────
# GEOGRAPHIC CHARTS
# ─────────────────────────────────────────────────────────────────────────────

def choropleth_map(
    df: pd.DataFrame,
    locations: str,
    color: str,
    title: str = "",
    colorscale: str = "Plasma",
    hover_data: Optional[List[str]] = None,
    height: int = 500,
) -> go.Figure:
    """
    Create a US state-level choropleth map.

    Args:
        df:         State-level DataFrame with abbreviations.
        locations:  Column with 2-letter state abbreviations.
        color:      Column to drive the colour intensity.
        title:      Chart title.
        colorscale: Plotly colorscale name.
        hover_data: Extra columns shown on hover.
        height:     Figure height.

    Returns:
        Plotly Figure.
    """
    fig = px.choropleth(
        df,
        locations=locations,
        color=color,
        locationmode="USA-states",
        scope="usa",
        hover_data=hover_data or [],
        color_continuous_scale=colorscale,
    )
    fig.update_layout(
        geo=dict(
            bgcolor="rgba(0,0,0,0)",
            lakecolor="rgba(0,0,0,0)",
            landcolor="rgba(30,33,48,0.6)",
            showlakes=True,
            showland=True,
            subunitcolor="rgba(154,160,185,0.3)",
        ),
        coloraxis_colorbar=dict(
            tickfont=dict(color=PALETTE["muted"]),
        ),
    )
    return _apply_base(fig, title=title, height=height)


def scattergeo_map(
    factory_df: pd.DataFrame,
    route_df: Optional[pd.DataFrame] = None,
    title: str = "Shipping Route Map",
    height: int = 560,
) -> go.Figure:
    """
    Create an interactive US scatter geo map showing factories and routes.

    Args:
        factory_df: DataFrame with factory data (lat, lon, Factory, shipments, etc.).
        route_df:   Optional route-level DataFrame with factory_lat, factory_lon,
                    state_lat, state_lon, state, shipments, avg_efficiency_score.
        title:      Chart title.
        height:     Figure height.

    Returns:
        Plotly Figure with factory markers and optional route lines.
    """
    fig = go.Figure()

    # Route lines (drawn first so factories render on top)
    if route_df is not None and not route_df.empty:
        for _, row in route_df.iterrows():
            efficiency = row.get("avg_efficiency_score", 0.5)
            line_color = (
                f"rgba(67,233,123,{0.3 + efficiency * 0.5})"
                if efficiency >= 0.5
                else f"rgba(252,92,125,{0.3 + (1 - efficiency) * 0.5})"
            )
            fig.add_trace(go.Scattergeo(
                lon=[row["factory_lon"], row["state_lon"]],
                lat=[row["factory_lat"], row["state_lat"]],
                mode="lines",
                line=dict(width=max(0.5, row.get("shipments", 1) / 300), color=line_color),
                showlegend=False,
                hoverinfo="skip",
            ))

    # Factory markers
    for _, row in factory_df.iterrows():
        factory_name = row["Factory"]
        color = FACTORY_COLOURS.get(factory_name, PALETTE["primary"])
        fig.add_trace(go.Scattergeo(
            lon=[row["lon"]],
            lat=[row["lat"]],
            mode="markers+text",
            name=factory_name,
            text=[factory_name.split()[0]],  # Short label
            textposition="top center",
            textfont=dict(size=10, color=PALETTE["text"]),
            marker=dict(
                size=14 + row.get("shipments", 0) / 800,
                color=color,
                symbol="star",
                line=dict(width=2, color="white"),
            ),
            hovertemplate=(
                f"<b>{factory_name}</b><br>"
                f"Shipments: {row.get('shipments', 'N/A')}<br>"
                f"States Served: {row.get('states_served', 'N/A')}<br>"
                f"Delay Rate: {row.get('delay_rate_pct', 'N/A'):.1f}%"
                "<extra></extra>"
            ),
        ))

    fig.update_geos(
        scope="usa",
        bgcolor="rgba(0,0,0,0)",
        lakecolor="#1E2130",
        landcolor="rgba(30,33,48,0.8)",
        showlakes=True,
        showland=True,
        subunitcolor="rgba(154,160,185,0.3)",
        countrycolor="rgba(154,160,185,0.3)",
        showcoastlines=True,
        coastlinecolor="rgba(154,160,185,0.3)",
    )
    _, base_layout, _, text_color = _get_theme_config()
    base = {k: v for k, v in base_layout.items() if k != "legend"}
    fig.update_layout(
        height=height,
        showlegend=True,
        legend=dict(
            title="Factories",
            bgcolor=base_layout["legend"]["bgcolor"],
            bordercolor=base_layout["legend"]["bordercolor"],
            borderwidth=1,
            font=dict(size=11, color=text_color),
        ),
        **base,
    )
    fig.update_layout(title=dict(
        text=title, font=dict(size=15, color=text_color), x=0.01
    ))
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD-SPECIFIC CHARTS
# ─────────────────────────────────────────────────────────────────────────────

def route_leaderboard_chart(
    df: pd.DataFrame,
    route_col: str = "route",
    score_col: str = "avg_efficiency_score",
    n: int = 10,
    ascending: bool = False,
    title: str = "Top Routes by Efficiency",
    height: int = 450,
) -> go.Figure:
    """
    Create a horizontal bar chart for the route leaderboard.

    Args:
        df:         Route summary DataFrame.
        route_col:  Column with route names.
        score_col:  Column with efficiency scores.
        n:          Number of routes to show.
        ascending:  Sort order (False = best first).
        title:      Chart title.
        height:     Figure height.

    Returns:
        Plotly Figure.
    """
    data = df.sort_values(score_col, ascending=ascending).head(n).copy()
    data = data.sort_values(score_col, ascending=True)  # horizontal bars top = best

    colors = [
        PALETTE["accent"] if s >= 0.6
        else PALETTE["warning"] if s >= 0.4
        else PALETTE["danger"]
        for s in data[score_col]
    ]

    fig = go.Figure(go.Bar(
        x=data[score_col],
        y=data[route_col].str.replace("\u2192", "->"),
        orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        text=data[score_col].round(3).astype(str),
        textposition="outside",
        textfont=dict(size=10, color=PALETTE["text"]),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Efficiency Score: %{x:.3f}<br>"
            "<extra></extra>"
        ),
    ))
    fig.update_xaxes(range=[0, 1.1])
    return _apply_base(fig, title=title, height=height)


def kpi_gauge(
    value: float,
    title: str = "",
    min_val: float = 0,
    max_val: float = 100,
    threshold_good: float = 70,
    threshold_warn: float = 40,
    suffix: str = "%",
    height: int = 260,
) -> go.Figure:
    """
    Create a gauge chart for a single KPI.

    Args:
        value:           The KPI value.
        title:           Gauge title.
        min_val:         Minimum scale value.
        max_val:         Maximum scale value.
        threshold_good:  Value above which colour is green.
        threshold_warn:  Value above which colour is yellow (below = red).
        suffix:          Unit suffix for the display value.
        height:          Figure height.

    Returns:
        Plotly Figure.
    """
    if value >= threshold_good:
        bar_color = PALETTE["accent"]
    elif value >= threshold_warn:
        bar_color = PALETTE["warning"]
    else:
        bar_color = PALETTE["danger"]

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number=dict(suffix=suffix, font=dict(size=28, color=PALETTE["text"])),
        gauge=dict(
            axis=dict(
                range=[min_val, max_val],
                tickwidth=1,
                tickcolor=PALETTE["muted"],
                tickfont=dict(color=PALETTE["muted"]),
            ),
            bar=dict(color=bar_color, thickness=0.25),
            bgcolor="rgba(30,33,48,0.5)",
            borderwidth=0,
            steps=[
                dict(range=[min_val, threshold_warn], color="rgba(252,92,125,0.15)"),
                dict(range=[threshold_warn, threshold_good], color="rgba(247,183,49,0.15)"),
                dict(range=[threshold_good, max_val], color="rgba(67,233,123,0.15)"),
            ],
            threshold=dict(
                line=dict(color=PALETTE["text"], width=2),
                thickness=0.75,
                value=value,
            ),
        ),
        title=dict(text=title, font=dict(size=13, color=PALETTE["muted"])),
    ))
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=PALETTE["text"], family="Inter, Roboto, sans-serif"),
        margin=dict(l=20, r=20, t=30, b=10),
    )
    return fig


def feature_importance_chart(
    df: pd.DataFrame,
    feature_col: str = "feature",
    importance_col: str = "importance",
    title: str = "Feature Importance",
    height: int = 400,
) -> go.Figure:
    """
    Create a horizontal bar chart of model feature importances.

    Args:
        df:             Feature importance DataFrame.
        feature_col:    Column with feature names.
        importance_col: Column with importance scores.
        title:          Chart title.
        height:         Figure height.

    Returns:
        Plotly Figure.
    """
    data = df.sort_values(importance_col, ascending=True)
    colors = px.colors.sample_colorscale(
        "Viridis", [i / max(len(data) - 1, 1) for i in range(len(data))]
    )
    fig = go.Figure(go.Bar(
        x=data[importance_col],
        y=data[feature_col],
        orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
    ))
    return _apply_base(fig, title=title, height=height)


def funnel_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str = "",
    height: int = 380,
) -> go.Figure:
    """
    Create a funnel chart (useful for mode/region pipeline comparisons).

    Args:
        df:     Data source.
        x:      Values column.
        y:      Labels column.
        title:  Chart title.
        height: Figure height.

    Returns:
        Plotly Figure.
    """
    fig = px.funnel(
        df.sort_values(x, ascending=False),
        x=x, y=y,
        color_discrete_sequence=QUALITATIVE_COLORS,
    )
    return _apply_base(fig, title=title, height=height)


def waterfall_chart(
    categories: List[str],
    values: List[float],
    title: str = "",
    height: int = 380,
) -> go.Figure:
    """
    Create a waterfall chart (for profit/cost decomposition).

    Args:
        categories: List of category labels.
        values:     List of numeric changes.
        title:      Chart title.
        height:     Figure height.

    Returns:
        Plotly Figure.
    """
    measure = ["relative"] * (len(categories) - 1) + ["total"]
    fig = go.Figure(go.Waterfall(
        name="",
        orientation="v",
        measure=measure,
        x=categories,
        y=values,
        connector=dict(line=dict(color=PALETTE["muted"], width=1)),
        increasing=dict(marker=dict(color=PALETTE["accent"])),
        decreasing=dict(marker=dict(color=PALETTE["danger"])),
        totals=dict(marker=dict(color=PALETTE["primary"])),
    ))
    return _apply_base(fig, title=title, height=height)


def sankey_diagram(
    df: pd.DataFrame,
    source_col: str,
    target_col: str,
    value_col: str,
    title: str = "Supply Chain Flow",
    height: int = 480,
) -> go.Figure:
    """Create an interactive Sankey diagram representing origin-to-destination shipment flow."""
    grouped = df.groupby([source_col, target_col])[value_col].sum().reset_index()
    all_nodes = list(pd.concat([grouped[source_col], grouped[target_col]]).unique())
    node_map = {node: i for i, node in enumerate(all_nodes)}

    sources = grouped[source_col].map(node_map).tolist()
    targets = grouped[target_col].map(node_map).tolist()
    values = grouped[value_col].tolist()

    node_colors = [
        QUALITATIVE_COLORS[i % len(QUALITATIVE_COLORS)] for i in range(len(all_nodes))
    ]

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="rgba(0,0,0,0.5)", width=0.5),
            label=all_nodes,
            color=node_colors,
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color="rgba(108, 99, 255, 0.25)",
        ),
    )])
    return _apply_base(fig, title=title, height=height)


def treemap_chart(
    df: pd.DataFrame,
    path: List[str],
    values: str,
    color: Optional[str] = None,
    title: str = "Hierarchical Distribution",
    height: int = 450,
) -> go.Figure:
    """Create a hierarchical Treemap chart (e.g. Division -> Product)."""
    fig = px.treemap(
        df,
        path=path,
        values=values,
        color=color or values,
        color_continuous_scale="Viridis",
    )
    fig.update_traces(textinfo="label+value+percent parent")
    return _apply_base(fig, title=title, height=height)


def radar_chart(
    categories: List[str],
    values: List[float],
    title: str = "Multi-Dimensional Scorecard",
    fill: str = "toself",
    height: int = 380,
) -> go.Figure:
    """Create a radar / spider chart for balanced scorecard comparison."""
    fig = go.Figure(data=go.Scatterpolar(
        r=values + [values[0]],
        theta=categories + [categories[0]],
        fill=fill,
        line=dict(color="#6C63FF", width=2),
        fillcolor="rgba(108, 99, 255, 0.2)",
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, max(values) * 1.15 if values else 100],
                gridcolor="rgba(154,160,185,0.2)",
            ),
            angularaxis=dict(gridcolor="rgba(154,160,185,0.2)"),
            bgcolor="rgba(0,0,0,0)",
        ),
    )
    return _apply_base(fig, title=title, height=height)

