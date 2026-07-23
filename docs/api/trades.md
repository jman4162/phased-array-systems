# Trades API

Design of Experiments, batch evaluation, and Pareto analysis.

## Overview

```python
from phased_array_systems.trades import (
    # Design Space
    DesignSpace,
    DesignVariable,

    # DOE Generation
    generate_doe,

    # Batch Evaluation
    BatchRunner,

    # Pareto Analysis
    filter_feasible,
    extract_pareto,
    rank_pareto,
)

# Additional functions via submodules
from phased_array_systems.trades.doe import generate_doe_from_dict, augment_doe
from phased_array_systems.trades.pareto import compute_hypervolume
```

## Design Space

::: phased_array_systems.trades.design_space.DesignSpace
    options:
      show_root_heading: true
      members_order: source

::: phased_array_systems.trades.design_space.DesignVariable
    options:
      show_root_heading: true
      members_order: source

## DOE Generation

::: phased_array_systems.trades.doe.generate_doe
    options:
      show_root_heading: true

::: phased_array_systems.trades.doe.generate_doe_from_dict
    options:
      show_root_heading: true

::: phased_array_systems.trades.doe.augment_doe
    options:
      show_root_heading: true

## Batch Evaluation

::: phased_array_systems.trades.runner.BatchRunner
    options:
      show_root_heading: true
      members_order: source

## Pareto Analysis

::: phased_array_systems.trades.pareto.filter_feasible
    options:
      show_root_heading: true

::: phased_array_systems.trades.pareto.extract_pareto
    options:
      show_root_heading: true

::: phased_array_systems.trades.pareto.rank_pareto
    options:
      show_root_heading: true

::: phased_array_systems.trades.pareto.compute_hypervolume
    options:
      show_root_heading: true

## Usage Examples

### Complete Trade Study

```python
from phased_array_systems.trades import (
    DesignSpace, generate_doe, BatchRunner,
    filter_feasible, extract_pareto, rank_pareto
)
from phased_array_systems.requirements import Requirement, RequirementSet

# Define design space
space = (
    DesignSpace(name="Array Trade")
    .add_variable("array.nx", type="categorical", values=[4, 8, 16])
    .add_variable("array.ny", type="categorical", values=[4, 8, 16])
    .add_variable("rf.tx_power_w_per_elem", type="float", low=0.5, high=3.0)
    # Fixed parameters
    .add_variable("array.geometry", type="categorical", values=["rectangular"])
    .add_variable("array.dx_lambda", type="float", low=0.5, high=0.5)
    .add_variable("array.dy_lambda", type="float", low=0.5, high=0.5)
    .add_variable("array.enforce_subarray_constraint", type="categorical", values=[True])
    .add_variable("rf.pa_efficiency", type="float", low=0.3, high=0.3)
)

# Define requirements
requirements = RequirementSet(requirements=[
    Requirement("REQ-001", "Min EIRP", "eirp_dbw", ">=", 35.0),
    Requirement("REQ-002", "Max Cost", "cost_usd", "<=", 100000.0),
])

# Generate DOE
doe = generate_doe(space, method="lhs", n_samples=100, seed=42)

# Run batch evaluation
runner = BatchRunner(scenario, requirements)
results = runner.run(doe, n_workers=1)

# Filter and extract Pareto
feasible = filter_feasible(results, requirements)
objectives = [("cost_usd", "minimize"), ("eirp_dbw", "maximize")]
pareto = extract_pareto(feasible, objectives)

# Rank Pareto designs
ranked = rank_pareto(pareto, objectives, weights=[0.5, 0.5])
print(f"Top design: {ranked.iloc[0]['case_id']}")
```

### Quick DOE

```python
doe = generate_doe_from_dict(
    {
        "array.nx": (4, 16, "int"),
        "array.ny": (4, 16, "int"),
        "rf.tx_power_w_per_elem": (0.5, 3.0),
        "array.geometry": ["rectangular", "triangular"],
    },
    n_samples=50,
    seed=42,
)
```

### Progress Callback

```python
def show_progress(completed, total):
    print(f"Progress: {completed}/{total} ({completed/total*100:.0f}%)")

results = runner.run(doe, progress_callback=show_progress)
```

### Hypervolume

```python
from phased_array_systems.trades import compute_hypervolume

hv = compute_hypervolume(pareto, objectives)
print(f"Hypervolume: {hv:.2e}")
```

## Type Aliases

```python
from phased_array_systems.types import OptimizeDirection

# OptimizeDirection = Literal["minimize", "maximize"]

objectives = [
    ("cost_usd", "minimize"),   # Lower is better
    ("eirp_dbw", "maximize"),   # Higher is better
]
```

## See Also

- [User Guide: Trade Studies](../user-guide/trade-studies.md)
- [User Guide: Pareto Analysis](../user-guide/pareto-analysis.md)
- [Visualization API](viz.md)

## Multi-Objective Optimization

::: phased_array_systems.trades.moo.optimize_pareto

## Global Sensitivity

::: phased_array_systems.trades.sensitivity.sobol_sensitivity
