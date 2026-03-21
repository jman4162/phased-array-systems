"""Plotting functions for trade study visualization."""

from typing import Literal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def pareto_plot(
    results: pd.DataFrame,
    x: str,
    y: str,
    pareto_front: pd.DataFrame | None = None,
    feasible_mask: pd.Series | None = None,
    color_by: str | None = None,
    size_by: str | None = None,
    ax: plt.Axes | None = None,
    title: str | None = None,
    x_label: str | None = None,
    y_label: str | None = None,
    show_pareto_line: bool = True,
    figsize: tuple[float, float] = (8, 6),
) -> plt.Figure:
    """Create a Pareto plot showing trade-offs between two objectives.

    Args:
        results: DataFrame with all evaluation results
        x: Column name for x-axis
        y: Column name for y-axis
        pareto_front: Optional DataFrame with Pareto-optimal points to highlight
        feasible_mask: Optional boolean Series marking feasible designs
        color_by: Optional column name to color points by
        size_by: Optional column name to size points by
        ax: Optional existing Axes to plot on
        title: Plot title
        x_label: X-axis label (defaults to column name)
        y_label: Y-axis label (defaults to column name)
        show_pareto_line: If True, draw line connecting Pareto points
        figsize: Figure size (width, height)

    Returns:
        matplotlib Figure object
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    # Determine point sizes
    if size_by is not None and size_by in results.columns:
        sizes = results[size_by]
        sizes = (sizes - sizes.min()) / (sizes.max() - sizes.min() + 1e-10) * 100 + 20
    else:
        sizes = 50

    # Determine colors
    if color_by is not None and color_by in results.columns:
        colors = results[color_by]
        cmap = plt.cm.viridis
    else:
        colors = "steelblue"
        cmap = None

    # Plot infeasible points (if mask provided)
    if feasible_mask is not None:
        infeasible = results[~feasible_mask]
        if len(infeasible) > 0:
            ax.scatter(
                infeasible[x],
                infeasible[y],
                c="lightgray",
                s=30,
                alpha=0.5,
                marker="x",
                label="Infeasible",
            )

    # Plot all feasible points
    plot_data = results[feasible_mask] if feasible_mask is not None else results

    scatter = ax.scatter(
        plot_data[x],
        plot_data[y],
        c=colors if color_by is None else plot_data[color_by],
        s=sizes if isinstance(sizes, int) else plot_data[size_by] if size_by else 50,
        alpha=0.7,
        cmap=cmap,
        label="Feasible" if feasible_mask is not None else None,
    )

    # Add colorbar if coloring by a metric
    if color_by is not None and cmap is not None:
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label(color_by)

    # Highlight Pareto front
    if pareto_front is not None and len(pareto_front) > 0:
        ax.scatter(
            pareto_front[x],
            pareto_front[y],
            facecolors="none",
            edgecolors="red",
            s=100,
            linewidths=2,
            label="Pareto Optimal",
            zorder=5,
        )

        # Draw Pareto line
        if show_pareto_line and len(pareto_front) > 1:
            sorted_pareto = pareto_front.sort_values(x)
            ax.plot(
                sorted_pareto[x],
                sorted_pareto[y],
                "r--",
                alpha=0.5,
                linewidth=1.5,
                zorder=4,
            )

    # Labels and title
    ax.set_xlabel(x_label or x)
    ax.set_ylabel(y_label or y)
    ax.set_title(title or f"Pareto Trade-off: {x} vs {y}")

    # Legend
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc="best")

    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    return fig


def scatter_matrix(
    results: pd.DataFrame,
    columns: list[str],
    color_by: str | None = None,
    diagonal: Literal["hist", "kde"] = "hist",
    figsize: tuple[float, float] | None = None,
    title: str | None = None,
) -> plt.Figure:
    """Create a scatter matrix showing pairwise relationships.

    Args:
        results: DataFrame with evaluation results
        columns: List of column names to include
        color_by: Optional column name to color points by
        diagonal: What to show on diagonal ("hist" or "kde")
        figsize: Figure size (auto-calculated if None)
        title: Overall figure title

    Returns:
        matplotlib Figure object
    """
    n = len(columns)
    if figsize is None:
        figsize = (n * 2.5, n * 2.5)

    fig, axes = plt.subplots(n, n, figsize=figsize)

    # Determine colors
    if color_by is not None and color_by in results.columns:
        colors = results[color_by].values
        cmap = plt.cm.viridis
        norm = plt.Normalize(colors.min(), colors.max())
        point_colors = cmap(norm(colors))
    else:
        point_colors = "steelblue"

    for i, col_i in enumerate(columns):
        for j, col_j in enumerate(columns):
            ax = axes[i, j]

            if i == j:
                # Diagonal: histogram or KDE
                if diagonal == "hist":
                    ax.hist(results[col_i], bins=20, alpha=0.7, color="steelblue")
                else:  # kde
                    from scipy import stats

                    data = results[col_i].dropna()
                    if len(data) > 1:
                        kde = stats.gaussian_kde(data)
                        x_range = np.linspace(data.min(), data.max(), 100)
                        ax.fill_between(x_range, kde(x_range), alpha=0.5)
                        ax.plot(x_range, kde(x_range), color="steelblue")
            else:
                # Off-diagonal: scatter plot
                ax.scatter(
                    results[col_j],
                    results[col_i],
                    c=point_colors,
                    s=10,
                    alpha=0.5,
                )

            # Labels on edges only
            if i == n - 1:
                ax.set_xlabel(col_j, fontsize=8)
            else:
                ax.set_xticklabels([])

            if j == 0:
                ax.set_ylabel(col_i, fontsize=8)
            else:
                ax.set_yticklabels([])

            ax.tick_params(labelsize=6)

    if title:
        fig.suptitle(title, fontsize=12)

    fig.tight_layout()
    if title:
        fig.subplots_adjust(top=0.95)

    return fig


def trade_space_plot(
    results: pd.DataFrame,
    x: str,
    y: str,
    z: str,
    feasible_mask: pd.Series | None = None,
    pareto_front: pd.DataFrame | None = None,
    ax: plt.Axes | None = None,
    figsize: tuple[float, float] = (10, 8),
    title: str | None = None,
) -> plt.Figure:
    """Create a 3D trade space visualization.

    Args:
        results: DataFrame with evaluation results
        x: Column name for x-axis
        y: Column name for y-axis
        z: Column name for z-axis (color)
        feasible_mask: Optional boolean mask for feasible designs
        pareto_front: Optional DataFrame with Pareto-optimal points
        ax: Optional existing 3D Axes
        figsize: Figure size
        title: Plot title

    Returns:
        matplotlib Figure object
    """
    if ax is None:
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(111, projection="3d")
    else:
        fig = ax.figure

    # Plot points
    if feasible_mask is not None:
        # Infeasible
        inf_data = results[~feasible_mask]
        ax.scatter(
            inf_data[x],
            inf_data[y],
            inf_data[z],
            c="lightgray",
            alpha=0.3,
            s=20,
            marker="x",
        )
        plot_data = results[feasible_mask]
    else:
        plot_data = results

    scatter = ax.scatter(
        plot_data[x],
        plot_data[y],
        plot_data[z],
        c=plot_data[z],
        cmap="viridis",
        alpha=0.7,
        s=40,
    )

    # Highlight Pareto front
    if pareto_front is not None and len(pareto_front) > 0:
        ax.scatter(
            pareto_front[x],
            pareto_front[y],
            pareto_front[z],
            c="red",
            s=100,
            marker="*",
            label="Pareto Optimal",
            zorder=5,
        )
        ax.legend()

    ax.set_xlabel(x)
    ax.set_ylabel(y)
    ax.set_zlabel(z)

    fig.colorbar(scatter, ax=ax, label=z, shrink=0.5)

    if title:
        ax.set_title(title)

    return fig


def tornado_plot(
    sensitivities: pd.DataFrame,
    metric_key: str,
    ax: plt.Axes | None = None,
    figsize: tuple[float, float] = (10, 6),
    title: str | None = None,
) -> plt.Figure:
    """Create a tornado diagram showing parameter sensitivity for one metric.

    Args:
        sensitivities: Output of compute_sensitivity_coefficients()
        metric_key: Which metric to plot (e.g., "g_peak_db")
        ax: Optional existing Axes to plot on
        figsize: Figure size
        title: Plot title

    Returns:
        matplotlib Figure object
    """
    # Filter to the target metric
    data = sensitivities[sensitivities["metric"] == metric_key].copy()
    if data.empty:
        if ax is None:
            fig, ax = plt.subplots(figsize=figsize)
        else:
            fig = ax.figure
        ax.text(
            0.5,
            0.5,
            f"No data for metric: {metric_key}",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        return fig

    # Sort by absolute sensitivity (most impactful at top)
    data = data.sort_values("sensitivity", ascending=True)

    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    y_pos = np.arange(len(data))
    baseline = data["baseline"].iloc[0]

    # Draw bars: left side = metric_min, right side = metric_max
    lefts = data["metric_min"].values - baseline
    rights = data["metric_max"].values - baseline

    colors_left = ["#2196F3" if v < 0 else "#FF5722" for v in lefts]
    colors_right = ["#FF5722" if v > 0 else "#2196F3" for v in rights]

    ax.barh(y_pos, lefts, align="center", color=colors_left, alpha=0.8, height=0.6)
    ax.barh(y_pos, rights, align="center", color=colors_right, alpha=0.8, height=0.6)

    # Reference line at zero (baseline)
    ax.axvline(x=0, color="black", linewidth=0.8)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(data["parameter"].values)
    ax.set_xlabel(f"Change in {metric_key} from baseline ({baseline:.2f})")
    ax.set_title(title or f"Sensitivity Tornado: {metric_key}")
    ax.grid(True, axis="x", alpha=0.3)

    fig.tight_layout()
    return fig


def save_figure(
    fig: plt.Figure,
    path: str,
    dpi: int = 150,
    transparent: bool = False,
) -> None:
    """Save a figure to file.

    Args:
        fig: matplotlib Figure to save
        path: Output path (extension determines format)
        dpi: Resolution for raster formats
        transparent: Whether to use transparent background
    """
    fig.savefig(path, dpi=dpi, transparent=transparent, bbox_inches="tight")
