"""Design optimization using scipy solvers.

This module wraps scipy.optimize solvers to find optimal designs within
a DesignSpace, using evaluate_case() as the objective function and
RequirementSet.verify() for constraint handling.

Supported solvers:
    - differential_evolution: Global optimizer, no gradients needed
    - dual_annealing: Global optimizer for rugged landscapes
    - minimize (L-BFGS-B): Local optimizer, fast but needs good initial point

Example:
    >>> from phased_array_systems.trades.optimization import optimize_design
    >>> result = optimize_design(
    ...     design_space=space,
    ...     scenario=scenario,
    ...     objectives=[("eirp_dbw", "maximize")],
    ...     method="differential_evolution",
    ... )
    >>> print(result.best_metrics["eirp_dbw"])
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import numpy as np

from phased_array_systems.architecture import Architecture
from phased_array_systems.evaluate import evaluate_case
from phased_array_systems.trades.design_space import DesignSpace
from phased_array_systems.types import MetricsDict

if TYPE_CHECKING:
    from phased_array_systems.requirements import RequirementSet
    from phased_array_systems.types import Scenario


@dataclass
class OptimizationResult:
    """Result of a design optimization run.

    Attributes:
        best_architecture: The optimal Architecture found
        best_metrics: Full metrics dictionary for the optimal design
        objective_value: Final scalar objective value
        n_evaluations: Number of evaluate_case() calls
        converged: Whether the solver reported convergence
        runtime_s: Wall-clock time in seconds
        design_history: Metrics from each evaluation (if tracked)
    """

    best_architecture: Architecture
    best_metrics: MetricsDict
    objective_value: float
    n_evaluations: int
    converged: bool
    runtime_s: float
    design_history: list[MetricsDict] = field(default_factory=list)


def _build_architecture_from_vector(
    x: np.ndarray,
    design_space: DesignSpace,
) -> Architecture:
    """Convert a flat parameter vector back to an Architecture.

    Rounds integer variables and maps categorical indices.
    """
    flat_dict: dict = {}
    for i, var in enumerate(design_space.variables):
        if var.type == "int":
            flat_dict[var.name] = int(round(x[i]))
        elif var.type == "categorical":
            idx = int(round(x[i]))
            idx = max(0, min(idx, len(var.values) - 1))
            flat_dict[var.name] = var.values[idx]
        else:
            flat_dict[var.name] = float(x[i])
    return Architecture.from_flat(flat_dict)


def _get_bounds(design_space: DesignSpace) -> list[tuple[float, float]]:
    """Extract scipy-compatible bounds from a DesignSpace."""
    bounds = []
    for var in design_space.variables:
        if var.type == "categorical":
            bounds.append((0.0, len(var.values) - 1.0))
        else:
            bounds.append((float(var.low), float(var.high)))
    return bounds


def _get_int_indices(design_space: DesignSpace) -> list[int]:
    """Get indices of integer and categorical variables."""
    return [i for i, var in enumerate(design_space.variables) if var.type in ("int", "categorical")]


def _make_objective(
    design_space: DesignSpace,
    scenario: Scenario,
    requirements: RequirementSet | None,
    objectives: list[tuple[str, str]],
    weights: list[float] | None,
    penalty_weight: float,
    track_history: bool,
    history: list[MetricsDict],
    eval_counter: list[int],
) -> callable:
    """Create a scipy-compatible objective function."""

    obj_weights = weights or [1.0] * len(objectives)
    # Normalize weights
    total_w = sum(obj_weights)
    obj_weights = [w / total_w for w in obj_weights]

    def objective(x: np.ndarray) -> float:
        eval_counter[0] += 1

        try:
            arch = _build_architecture_from_vector(x, design_space)
            metrics = evaluate_case(arch, scenario, requirements)
        except Exception:
            return 1e12  # Infeasible

        if track_history:
            history.append(dict(metrics))

        # Compute scalarized objective
        obj_value = 0.0
        for (metric, sense), w in zip(objectives, obj_weights, strict=True):
            val = metrics.get(metric)
            if val is None or not isinstance(val, (int, float)):
                return 1e12

            if sense == "maximize":
                obj_value -= w * float(val)
            else:  # minimize
                obj_value += w * float(val)

        # Constraint penalty from requirements
        if requirements is not None and len(requirements) > 0:
            report = requirements.verify(metrics)
            if not report.passes:
                penalty = 0.0
                for result in report.results:
                    if not result.passes and result.margin is not None:
                        penalty += abs(result.margin)
                    elif not result.passes:
                        penalty += 100.0  # Missing metric penalty
                obj_value += penalty_weight * penalty

        return obj_value

    return objective


def optimize_design(
    design_space: DesignSpace,
    scenario: Scenario,
    objectives: list[tuple[str, str]],
    requirements: RequirementSet | None = None,
    weights: list[float] | None = None,
    method: Literal[
        "differential_evolution", "dual_annealing", "minimize"
    ] = "differential_evolution",
    seed: int | None = None,
    max_iter: int = 200,
    penalty_weight: float = 100.0,
    track_history: bool = False,
) -> OptimizationResult:
    """Find the optimal design within a design space.

    Args:
        design_space: DesignSpace defining variable bounds and types
        scenario: Scenario to evaluate against
        objectives: List of (metric_key, "minimize"/"maximize") tuples
        requirements: Optional requirements used as constraints (penalty)
        weights: Optional weights for multi-objective scalarization
            (defaults to equal weights). Must match len(objectives).
        method: Optimization solver to use:
            - "differential_evolution": Global, gradient-free (recommended)
            - "dual_annealing": Global, for rugged landscapes
            - "minimize": Local (L-BFGS-B), fast but may find local optima
        seed: Random seed for reproducibility
        max_iter: Maximum iterations for the solver
        penalty_weight: Weight for constraint violation penalty
        track_history: If True, store metrics from every evaluation

    Returns:
        OptimizationResult with the best design found

    Raises:
        ValueError: If objectives list is empty or weights length mismatches
    """
    if not objectives:
        raise ValueError("At least one objective is required")
    if weights is not None and len(weights) != len(objectives):
        raise ValueError(
            f"weights length ({len(weights)}) must match objectives length ({len(objectives)})"
        )

    bounds = _get_bounds(design_space)
    int_indices = _get_int_indices(design_space)
    history: list[MetricsDict] = []
    eval_counter = [0]

    objective_fn = _make_objective(
        design_space=design_space,
        scenario=scenario,
        requirements=requirements,
        objectives=objectives,
        weights=weights,
        penalty_weight=penalty_weight,
        track_history=track_history,
        history=history,
        eval_counter=eval_counter,
    )

    start_time = time.perf_counter()

    if method == "differential_evolution":
        from scipy.optimize import differential_evolution

        result = differential_evolution(
            objective_fn,
            bounds=bounds,
            seed=seed,
            maxiter=max_iter,
            integrality=[i in int_indices for i in range(len(bounds))],
            tol=1e-6,
            polish=False,
        )
        converged = result.success
        best_x = result.x

    elif method == "dual_annealing":
        from scipy.optimize import dual_annealing

        result = dual_annealing(
            objective_fn,
            bounds=bounds,
            seed=seed,
            maxiter=max_iter,
        )
        converged = result.success
        best_x = result.x
        # Round integer variables since dual_annealing doesn't support integrality
        for idx in int_indices:
            best_x[idx] = round(best_x[idx])

    elif method == "minimize":
        from scipy.optimize import minimize

        # Start from midpoint of bounds
        x0 = np.array([(lo + hi) / 2 for lo, hi in bounds])
        for idx in int_indices:
            x0[idx] = round(x0[idx])

        result = minimize(
            objective_fn,
            x0=x0,
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": max_iter},
        )
        converged = result.success
        best_x = result.x
        for idx in int_indices:
            best_x[idx] = round(best_x[idx])

    else:
        raise ValueError(f"Unknown method: {method}")

    elapsed = time.perf_counter() - start_time

    # Rebuild the best architecture and get final metrics
    best_arch = _build_architecture_from_vector(best_x, design_space)
    best_metrics = evaluate_case(best_arch, scenario, requirements)

    return OptimizationResult(
        best_architecture=best_arch,
        best_metrics=best_metrics,
        objective_value=float(result.fun),
        n_evaluations=eval_counter[0],
        converged=converged,
        runtime_s=elapsed,
        design_history=history if track_history else [],
    )
