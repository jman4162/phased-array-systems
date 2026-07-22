"""Design space definition for DOE studies."""

from typing import Any, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, model_validator


class DesignVariable(BaseModel):
    """Definition of a single design variable.

    Supports continuous (float), discrete (int), and categorical variables.

    Attributes:
        name: Variable name, typically a dot-path like "array.nx"
        type: Variable type ("int", "float", or "categorical")
        low: Lower bound for continuous/discrete variables
        high: Upper bound for continuous/discrete variables
        values: List of allowed values for categorical variables
    """

    name: str = Field(description="Variable name (e.g., 'array.nx')")
    type: Literal["int", "float", "categorical"] = "float"
    low: float | None = Field(default=None, description="Lower bound")
    high: float | None = Field(default=None, description="Upper bound")
    values: list[Any] | None = Field(default=None, description="Categorical values")

    @model_validator(mode="after")
    def validate_bounds_or_values(self) -> "DesignVariable":
        """Ensure proper bounds/values are set based on type."""
        if self.type in ("int", "float"):
            if self.low is None or self.high is None:
                raise ValueError(f"Variable '{self.name}': low and high required for {self.type}")
            if self.low > self.high:
                raise ValueError(f"Variable '{self.name}': low must be <= high")
        elif self.type == "categorical":
            if not self.values or len(self.values) < 1:
                raise ValueError(f"Variable '{self.name}': values required for categorical")
        return self

    def sample_uniform(self, n: int, rng: np.random.Generator) -> np.ndarray:
        """Generate uniform random samples.

        Args:
            n: Number of samples
            rng: NumPy random generator

        Returns:
            Array of sampled values
        """
        if self.type == "float":
            assert self.low is not None and self.high is not None
            return rng.uniform(self.low, self.high, n)
        elif self.type == "int":
            assert self.low is not None and self.high is not None
            return rng.integers(int(self.low), int(self.high) + 1, n)
        else:  # categorical
            assert self.values is not None
            indices = rng.integers(0, len(self.values), n)
            return np.array([self.values[i] for i in indices])

    def scale_from_unit(self, unit_values: np.ndarray) -> np.ndarray:
        """Scale values from [0, 1] to actual variable range.

        Args:
            unit_values: Values in [0, 1]

        Returns:
            Scaled values in variable's actual range
        """
        if self.type == "float":
            assert self.low is not None and self.high is not None
            return self.low + unit_values * (self.high - self.low)
        elif self.type == "int":
            assert self.low is not None and self.high is not None
            scaled = self.low + unit_values * (self.high - self.low + 1)
            return np.asarray(np.floor(scaled).astype(int).clip(int(self.low), int(self.high)))
        else:  # categorical
            assert self.values is not None
            indices = np.floor(unit_values * len(self.values)).astype(int)
            indices = indices.clip(0, len(self.values) - 1)
            return np.array([self.values[i] for i in indices])

    def get_grid_values(self, n_levels: int) -> list[Any]:
        """Get grid values for this variable.

        Args:
            n_levels: Number of levels for grid

        Returns:
            List of values at each level
        """
        if self.type == "float":
            assert self.low is not None and self.high is not None
            return list(np.linspace(self.low, self.high, n_levels))
        elif self.type == "int":
            assert self.low is not None and self.high is not None
            # For integers, use actual integer values
            all_ints = list(range(int(self.low), int(self.high) + 1))
            if len(all_ints) <= n_levels:
                return all_ints
            # Subsample evenly
            indices = np.linspace(0, len(all_ints) - 1, n_levels).astype(int)
            return [all_ints[i] for i in indices]
        else:  # categorical
            assert self.values is not None
            return list(self.values)


class DesignSpace(BaseModel):
    """Collection of design variables defining a design space.

    Provides methods for sampling the design space using various
    DOE methods (grid, random, LHS).

    Attributes:
        variables: List of design variables
        name: Optional name for the design space
    """

    variables: list[DesignVariable] = Field(default_factory=list)
    name: str | None = None

    def add_variable(
        self,
        name: str,
        type: Literal["int", "float", "categorical"] = "float",
        low: float | None = None,
        high: float | None = None,
        values: list[Any] | None = None,
    ) -> "DesignSpace":
        """Add a variable to the design space (fluent interface).

        Args:
            name: Variable name
            type: Variable type
            low: Lower bound
            high: Upper bound
            values: Categorical values

        Returns:
            Self for chaining
        """
        var = DesignVariable(name=name, type=type, low=low, high=high, values=values)
        self.variables.append(var)
        return self

    @property
    def n_dims(self) -> int:
        """Number of dimensions (variables) in the design space."""
        return len(self.variables)

    @property
    def variable_names(self) -> list[str]:
        """List of variable names."""
        return [v.name for v in self.variables]

    def sample(
        self,
        method: Literal["grid", "random", "lhs"] = "lhs",
        n_samples: int = 100,
        seed: int | None = None,
        grid_levels: int | list[int] | None = None,
    ) -> pd.DataFrame:
        """Sample the design space.

        Args:
            method: Sampling method ("grid", "random", "lhs")
            n_samples: Number of samples (ignored for grid method)
            seed: Random seed for reproducibility
            grid_levels: Number of levels per variable for grid method

        Returns:
            DataFrame with columns for each variable plus 'case_id'
        """
        if method == "grid":
            return self._sample_grid(grid_levels)
        elif method == "random":
            return self._sample_random(n_samples, seed)
        elif method == "lhs":
            return self._sample_lhs(n_samples, seed)
        else:
            raise ValueError(f"Unknown sampling method: {method}")

    def _sample_grid(self, grid_levels: int | list[int] | None) -> pd.DataFrame:
        """Generate full factorial grid."""
        if grid_levels is None:
            grid_levels = 3  # Default

        if isinstance(grid_levels, int):
            levels_per_var = [grid_levels] * len(self.variables)
        else:
            levels_per_var = grid_levels

        # Generate grid values for each variable
        var_values = []
        for var, n_levels in zip(self.variables, levels_per_var, strict=True):
            var_values.append(var.get_grid_values(n_levels))

        # Create full factorial grid using meshgrid
        grids = np.meshgrid(*var_values, indexing="ij")
        flat_grids = [g.flatten() for g in grids]

        # Build DataFrame
        data = {var.name: flat_grids[i] for i, var in enumerate(self.variables)}
        df = pd.DataFrame(data)

        # Add case IDs
        df.insert(0, "case_id", [f"case_{i:05d}" for i in range(len(df))])

        return df

    def _sample_random(self, n_samples: int, seed: int | None) -> pd.DataFrame:
        """Generate random samples."""
        rng = np.random.default_rng(seed)

        data = {}
        for var in self.variables:
            data[var.name] = var.sample_uniform(n_samples, rng)

        df = pd.DataFrame(data)
        df.insert(0, "case_id", [f"case_{i:05d}" for i in range(len(df))])

        return df

    def _sample_lhs(self, n_samples: int, seed: int | None) -> pd.DataFrame:
        """Generate Latin Hypercube samples."""
        from scipy.stats import qmc

        # Generate LHS in unit hypercube
        sampler = qmc.LatinHypercube(d=len(self.variables), seed=seed)
        unit_samples = sampler.random(n_samples)

        # Scale to actual variable ranges
        data = {}
        for i, var in enumerate(self.variables):
            data[var.name] = var.scale_from_unit(unit_samples[:, i])

        df = pd.DataFrame(data)
        df.insert(0, "case_id", [f"case_{i:05d}" for i in range(len(df))])

        return df

    def get_variable(self, name: str) -> DesignVariable | None:
        """Get a variable by name."""
        for var in self.variables:
            if var.name == name:
                return var
        return None
