"""Design of Experiments (DOE) generation utilities."""

from typing import Literal

import pandas as pd

from phased_array_systems.trades.design_space import DesignSpace


def generate_doe(
    design_space: DesignSpace,
    method: Literal["grid", "random", "lhs"] = "lhs",
    n_samples: int = 100,
    seed: int | None = None,
    grid_levels: int | list[int] | None = None,
) -> pd.DataFrame:
    """Generate a Design of Experiments from a design space.

    This is a convenience function that wraps DesignSpace.sample().

    Args:
        design_space: DesignSpace defining the variables and bounds
        method: Sampling method
            - "grid": Full factorial grid (n_samples ignored)
            - "random": Uniform random sampling
            - "lhs": Latin Hypercube Sampling (space-filling)
        n_samples: Number of samples (for random/lhs methods)
        seed: Random seed for reproducibility
        grid_levels: Number of levels per variable for grid method

    Returns:
        DataFrame with columns:
            - case_id: Unique identifier for each case
            - One column per design variable

    Examples:
        >>> space = DesignSpace()
        >>> space.add_variable("array.nx", "int", low=4, high=16)
        >>> space.add_variable("array.ny", "int", low=4, high=16)
        >>> space.add_variable("rf.tx_power_w_per_elem", "float", low=0.5, high=2.0)
        >>> doe = generate_doe(space, method="lhs", n_samples=50, seed=42)
    """
    return design_space.sample(
        method=method,
        n_samples=n_samples,
        seed=seed,
        grid_levels=grid_levels,
    )


def generate_doe_from_dict(
    variables: dict,
    method: Literal["grid", "random", "lhs"] = "lhs",
    n_samples: int = 100,
    seed: int | None = None,
) -> pd.DataFrame:
    """Generate DOE from a simplified dictionary specification.

    Convenience function for quick DOE generation without creating
    explicit DesignVariable objects.

    Args:
        variables: Dictionary mapping variable names to specs:
            - For continuous: {"name": (low, high)} or {"name": (low, high, "float")}
            - For discrete: {"name": (low, high, "int")}
            - For categorical: {"name": ["value1", "value2", ...]}
        method: Sampling method
        n_samples: Number of samples
        seed: Random seed

    Returns:
        DataFrame with DOE cases

    Examples:
        >>> doe = generate_doe_from_dict({
        ...     "array.nx": (4, 16, "int"),
        ...     "array.ny": (4, 16, "int"),
        ...     "rf.tx_power_w_per_elem": (0.5, 2.0),
        ...     "array.geometry": ["rectangular", "triangular"],
        ... }, n_samples=50)
    """
    space = DesignSpace()

    for name, spec in variables.items():
        if isinstance(spec, list):
            # Categorical
            space.add_variable(name, type="categorical", values=spec)
        elif isinstance(spec, tuple):
            if len(spec) == 2:
                # (low, high) -> float
                space.add_variable(name, type="float", low=spec[0], high=spec[1])
            elif len(spec) == 3:
                # (low, high, type)
                space.add_variable(name, type=spec[2], low=spec[0], high=spec[1])
            else:
                raise ValueError(f"Invalid spec for '{name}': {spec}")
        else:
            raise ValueError(f"Invalid spec type for '{name}': {type(spec)}")

    return generate_doe(space, method=method, n_samples=n_samples, seed=seed)


def augment_doe(
    existing_doe: pd.DataFrame,
    design_space: DesignSpace,
    n_additional: int,
    method: Literal["random", "lhs"] = "lhs",
    seed: int | None = None,
) -> pd.DataFrame:
    """Add additional samples to an existing DOE.

    Useful for adaptive sampling or expanding a study.

    Args:
        existing_doe: Existing DOE DataFrame
        design_space: DesignSpace defining the variables
        n_additional: Number of additional samples to add
        method: Sampling method for new samples
        seed: Random seed

    Returns:
        Combined DataFrame with original + new cases
    """
    # Generate new samples
    new_doe = generate_doe(
        design_space,
        method=method,
        n_samples=n_additional,
        seed=seed,
    )

    # Renumber case IDs to avoid collision
    max_existing_id = 0
    for case_id in existing_doe["case_id"]:
        if case_id.startswith("case_"):
            try:
                num = int(case_id.replace("case_", ""))
                max_existing_id = max(max_existing_id, num)
            except ValueError:
                pass

    new_ids = [
        f"case_{i:05d}" for i in range(max_existing_id + 1, max_existing_id + 1 + n_additional)
    ]
    new_doe["case_id"] = new_ids

    # Combine
    return pd.concat([existing_doe, new_doe], ignore_index=True)
