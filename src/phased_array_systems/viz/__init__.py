"""Visualization utilities for trade study results."""

from phased_array_systems.viz.plots import pareto_plot, scatter_matrix, trade_space_plot

__all__ = [
    "pareto_plot",
    "scatter_matrix",
    "trade_space_plot",
]

# Interactive plotly variants live in phased_array_systems.viz.interactive
# and require the [plotting] extra; imported lazily to keep matplotlib-only
# installs working.
