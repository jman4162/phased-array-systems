# Visualization API

Plotting functions for trade study visualization.

## Overview

```python
from phased_array_systems.viz import pareto_plot, scatter_matrix, trade_space_plot

# Also available from submodule
from phased_array_systems.viz.plots import save_figure
```

## Functions

::: phased_array_systems.viz.plots.pareto_plot
    options:
      show_root_heading: true

::: phased_array_systems.viz.plots.scatter_matrix
    options:
      show_root_heading: true

::: phased_array_systems.viz.plots.trade_space_plot
    options:
      show_root_heading: true

::: phased_array_systems.viz.plots.save_figure
    options:
      show_root_heading: true

## Usage Examples

### Pareto Plot

```python
from phased_array_systems.viz import pareto_plot
from phased_array_systems.trades import extract_pareto

# Extract Pareto frontier
pareto = extract_pareto(results, [("cost_usd", "minimize"), ("eirp_dbw", "maximize")])

# Create feasibility mask
feasible_mask = results["verification.passes"] == 1.0

# Generate plot
fig = pareto_plot(
    results,
    x="cost_usd",
    y="eirp_dbw",
    pareto_front=pareto,
    feasible_mask=feasible_mask,
    color_by="link_margin_db",
    title="Cost vs EIRP Trade Space",
    x_label="Total Cost (USD)",
    y_label="EIRP (dBW)",
)
fig.savefig("pareto.png", dpi=150, bbox_inches="tight")
```

### Scatter Matrix

```python
from phased_array_systems.viz import scatter_matrix

fig = scatter_matrix(
    feasible,
    columns=["cost_usd", "eirp_dbw", "link_margin_db", "prime_power_w"],
    color_by="n_elements",
    diagonal="hist",
    title="Trade Space Correlations",
)
fig.savefig("scatter.png", dpi=150)
```

### 3D Trade Space

```python
from phased_array_systems.viz import trade_space_plot

fig = trade_space_plot(
    results,
    x="cost_usd",
    y="eirp_dbw",
    z="prime_power_w",
    feasible_mask=feasible_mask,
    pareto_front=pareto_3d,
    title="3D Trade Space",
)
fig.savefig("trade_space_3d.png", dpi=150)
```

### Multi-Panel Figure

```python
import matplotlib.pyplot as plt

fig, axes = plt.subplots(1, 2, figsize=(14, 6))

pareto_plot(results, x="cost_usd", y="eirp_dbw", ax=axes[0])
pareto_plot(results, x="cost_usd", y="link_margin_db", ax=axes[1])

fig.tight_layout()
fig.savefig("combined.png", dpi=150)
```

### Saving Figures

```python
from phased_array_systems.viz import save_figure

fig = pareto_plot(results, x="cost_usd", y="eirp_dbw")

# Various formats
save_figure(fig, "plot.png", dpi=150)
save_figure(fig, "plot.pdf")
save_figure(fig, "plot.svg")
save_figure(fig, "plot_transparent.png", transparent=True)
```

## Plot Customization

### Adding Annotations

```python
fig = pareto_plot(results, x="cost_usd", y="eirp_dbw")
ax = fig.axes[0]

# Add reference lines
ax.axhline(y=40, color='r', linestyle='--', label='Min EIRP')
ax.axvline(x=50000, color='g', linestyle='--', label='Budget')

# Add annotation
ax.annotate(
    "Target Region",
    xy=(40000, 45),
    xytext=(55000, 50),
    arrowprops=dict(arrowstyle="->"),
)

ax.legend()
```

### Custom Color Maps

```python
fig = pareto_plot(
    results,
    x="cost_usd",
    y="eirp_dbw",
    color_by="link_margin_db",
)

# Access scatter for custom colorbar
ax = fig.axes[0]
# Colorbar is automatically added when color_by is specified
```

## Non-Interactive Usage

For scripts without display:

```python
import matplotlib
matplotlib.use("Agg")  # Must be before pyplot import
import matplotlib.pyplot as plt

from phased_array_systems.viz import pareto_plot

fig = pareto_plot(results, x="cost_usd", y="eirp_dbw")
fig.savefig("output.png", dpi=150)
plt.close(fig)  # Release memory
```

## See Also

- [User Guide: Visualization](../user-guide/visualization.md)
- [User Guide: Pareto Analysis](../user-guide/pareto-analysis.md)
- [Trades API](trades.md)

## Interactive Plots (plotly)

::: phased_array_systems.viz.interactive.pareto_plot_interactive

::: phased_array_systems.viz.interactive.trade_space_plot_interactive

::: phased_array_systems.viz.interactive.figure_to_html_div
