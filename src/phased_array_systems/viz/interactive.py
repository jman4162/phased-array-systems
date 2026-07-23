"""Interactive plotly figures for trade studies (optional [plotting] extra).

API mirrors viz/plots.py; figures return plotly.graph_objects.Figure with
per-point hover text (case_id + key metrics) and embed self-contained into
HTML reports.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def _require_plotly() -> Any:
    try:
        import plotly.graph_objects as go
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "plotly is required for interactive plots. Install the plotting "
            'extra: pip install "phased-array-systems[plotting]"'
        ) from e
    return go


def _hover_text(df: pd.DataFrame, columns: list[str]) -> list[str]:
    texts = []
    for _, row in df.iterrows():
        parts = []
        if "case_id" in df.columns:
            parts.append(f"<b>{row['case_id']}</b>")
        for col in columns:
            val = row.get(col)
            if isinstance(val, float):
                parts.append(f"{col}: {val:.3f}")
            elif val is not None:
                parts.append(f"{col}: {val}")
        texts.append("<br>".join(parts))
    return texts


def pareto_plot_interactive(
    results: pd.DataFrame,
    x: str,
    y: str,
    pareto_front: pd.DataFrame | None = None,
    feasible_mask: pd.Series | None = None,
    color_by: str | None = None,
    title: str | None = None,
) -> Any:
    """Interactive 2-D trade plot with optional Pareto front overlay.

    Args:
        results: DataFrame with evaluation results
        x: Column for the x axis
        y: Column for the y axis
        pareto_front: Optional DataFrame of Pareto-optimal rows to highlight
        feasible_mask: Optional boolean Series; infeasible points greyed out
        color_by: Optional column to color points by (continuous colorbar)
        title: Plot title

    Returns:
        plotly.graph_objects.Figure
    """
    go = _require_plotly()

    hover_cols = [c for c in (x, y, color_by) if c]
    fig = go.Figure()

    if feasible_mask is not None:
        infeasible = results[~feasible_mask]
        if len(infeasible):
            fig.add_trace(
                go.Scatter(
                    x=infeasible[x],
                    y=infeasible[y],
                    mode="markers",
                    name="Infeasible",
                    marker={"color": "lightgray", "symbol": "x", "size": 7},
                    text=_hover_text(infeasible, hover_cols),
                    hoverinfo="text",
                )
            )
        plot_data = results[feasible_mask]
    else:
        plot_data = results

    marker: dict[str, Any] = {"size": 9, "opacity": 0.8}
    if color_by is not None and color_by in plot_data.columns:
        marker.update(
            color=plot_data[color_by],
            colorscale="Viridis",
            colorbar={"title": color_by},
            showscale=True,
        )
    else:
        marker["color"] = "steelblue"

    fig.add_trace(
        go.Scatter(
            x=plot_data[x],
            y=plot_data[y],
            mode="markers",
            name="Feasible" if feasible_mask is not None else "Designs",
            marker=marker,
            text=_hover_text(plot_data, hover_cols),
            hoverinfo="text",
        )
    )

    if pareto_front is not None and len(pareto_front):
        front = pareto_front.sort_values(x)
        fig.add_trace(
            go.Scatter(
                x=front[x],
                y=front[y],
                mode="markers+lines",
                name="Pareto optimal",
                marker={"color": "crimson", "size": 12, "symbol": "star"},
                line={"color": "crimson", "dash": "dash", "width": 1},
                text=_hover_text(front, hover_cols),
                hoverinfo="text",
            )
        )

    fig.update_layout(
        title=title or f"Trade-off: {x} vs {y}",
        xaxis_title=x,
        yaxis_title=y,
        template="plotly_white",
        legend={"orientation": "h", "y": -0.15},
    )
    return fig


def trade_space_plot_interactive(
    results: pd.DataFrame,
    x: str,
    y: str,
    z: str,
    feasible_mask: pd.Series | None = None,
    pareto_front: pd.DataFrame | None = None,
    title: str | None = None,
) -> Any:
    """Interactive 3-D trade-space scatter.

    Args:
        results: DataFrame with evaluation results
        x: Column for the x axis
        y: Column for the y axis
        z: Column for the z axis (also colors the points)
        feasible_mask: Optional boolean Series; infeasible points greyed out
        pareto_front: Optional DataFrame of Pareto-optimal rows to highlight
        title: Plot title

    Returns:
        plotly.graph_objects.Figure
    """
    go = _require_plotly()

    hover_cols = [x, y, z]
    fig = go.Figure()

    if feasible_mask is not None:
        infeasible = results[~feasible_mask]
        if len(infeasible):
            fig.add_trace(
                go.Scatter3d(
                    x=infeasible[x],
                    y=infeasible[y],
                    z=infeasible[z],
                    mode="markers",
                    name="Infeasible",
                    marker={"color": "lightgray", "symbol": "x", "size": 3},
                    text=_hover_text(infeasible, hover_cols),
                    hoverinfo="text",
                )
            )
        plot_data = results[feasible_mask]
    else:
        plot_data = results

    fig.add_trace(
        go.Scatter3d(
            x=plot_data[x],
            y=plot_data[y],
            z=plot_data[z],
            mode="markers",
            name="Designs",
            marker={
                "size": 4,
                "color": plot_data[z],
                "colorscale": "Viridis",
                "colorbar": {"title": z},
                "opacity": 0.75,
            },
            text=_hover_text(plot_data, hover_cols),
            hoverinfo="text",
        )
    )

    if pareto_front is not None and len(pareto_front):
        fig.add_trace(
            go.Scatter3d(
                x=pareto_front[x],
                y=pareto_front[y],
                z=pareto_front[z],
                mode="markers",
                name="Pareto optimal",
                marker={"color": "crimson", "size": 7, "symbol": "diamond"},
                text=_hover_text(pareto_front, hover_cols),
                hoverinfo="text",
            )
        )

    fig.update_layout(
        title=title or f"Trade space: {x} / {y} / {z}",
        scene={"xaxis_title": x, "yaxis_title": y, "zaxis_title": z},
        template="plotly_white",
    )
    return fig


def figure_to_html_div(fig: Any) -> str:
    """Render a plotly figure as a self-contained HTML fragment.

    plotly.js is inlined (no CDN), so reports remain single-file and
    viewable offline.
    """
    html = fig.to_html(full_html=False, include_plotlyjs="inline")
    return str(html)
