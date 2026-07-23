"""True multi-objective optimization via pymoo NSGA-II.

Returns the nondominated set directly instead of scalarizing with a-priori
weights (trades/optimization.py). Requires the optional [mdao] extra:

    pip install "phased-array-systems[mdao]"
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from phased_array_systems.evaluate import evaluate_case
from phased_array_systems.trades.design_space import DesignSpace
from phased_array_systems.trades.runner import default_architecture_builder
from phased_array_systems.types import OptimizeDirection, Scenario

if TYPE_CHECKING:
    from phased_array_systems.requirements import RequirementSet

_WORST = 1e12


def _require_pymoo() -> Any:
    try:
        import pymoo
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "pymoo is required for optimize_pareto. Install the MDAO extra: "
            'pip install "phased-array-systems[mdao]"'
        ) from e
    return pymoo


def _pymoo_vars(design_space: DesignSpace) -> dict[str, Any]:
    """Map DesignVariable types onto pymoo mixed-variable types."""
    from pymoo.core.variable import Choice, Integer, Real

    vars_: dict[str, Any] = {}
    for var in design_space.variables:
        if var.type == "float":
            assert var.low is not None and var.high is not None
            vars_[var.name] = Real(bounds=(var.low, var.high))
        elif var.type == "int":
            assert var.low is not None and var.high is not None
            vars_[var.name] = Integer(bounds=(int(var.low), int(var.high)))
        else:
            assert var.values is not None
            vars_[var.name] = Choice(options=list(var.values))
    return vars_


def optimize_pareto(
    design_space: DesignSpace,
    scenario: Scenario,
    objectives: list[tuple[str, OptimizeDirection]],
    requirements: RequirementSet | None = None,
    n_generations: int = 100,
    pop_size: int = 50,
    seed: int | None = None,
    verbose: bool = False,
) -> pd.DataFrame:
    """Find the Pareto front with NSGA-II (mixed-variable).

    Requirements with severity "must" become inequality constraints via
    normalized margins (g = -margin / max(|threshold|, 1)); constraint
    domination handles feasibility without penalty tuning. "should" and
    "nice" requirements do not constrain the search.

    Args:
        design_space: DesignSpace with float/int/categorical variables
        scenario: Scenario to evaluate against
        objectives: List of (metric_key, "minimize"/"maximize") tuples
        requirements: Optional requirement set (must-severity constrains)
        n_generations: Number of NSGA-II generations
        pop_size: Population size
        seed: Random seed for reproducibility
        verbose: Print pymoo progress

    Returns:
        DataFrame of nondominated designs: case_id, one column per design
        variable, plus the full metrics dict per point (same schema as
        BatchRunner output, so pareto plots and reports work unchanged).

    Raises:
        ImportError: If pymoo is not installed
        ValueError: If objectives is empty or a metric is missing
    """
    _require_pymoo()

    from pymoo.algorithms.moo.nsga2 import NSGA2
    from pymoo.core.mixed import (
        MixedVariableDuplicateElimination,
        MixedVariableMating,
        MixedVariableSampling,
    )
    from pymoo.core.problem import ElementwiseProblem
    from pymoo.optimize import minimize as pymoo_minimize

    if not objectives:
        raise ValueError("At least one objective is required")

    must_reqs = (
        [r for r in requirements.requirements if r.severity == "must"] if requirements else []
    )

    def _evaluate_row(row: dict[str, Any]) -> tuple[list[float], list[float]]:
        """Return (F, G) for one design point; worst-case on failure."""
        try:
            arch = default_architecture_builder(row)
            metrics = evaluate_case(arch, scenario)
        except Exception:
            return [_WORST] * len(objectives), [_WORST] * max(1, len(must_reqs))

        f = []
        for key, direction in objectives:
            val = metrics.get(key)
            if not isinstance(val, (int, float)):
                f.append(_WORST)
                continue
            f.append(-float(val) if direction == "maximize" else float(val))

        g = []
        for req in must_reqs:
            actual = metrics.get(req.metric_key)
            if not isinstance(actual, (int, float)):
                g.append(_WORST)
                continue
            margin = req.compute_margin(float(actual))
            scale = max(abs(req.value), 1.0)
            g.append(-margin / scale)  # feasible iff g <= 0
        if not must_reqs:
            g = [0.0]

        return f, g

    class _TradeProblem(ElementwiseProblem):
        def __init__(self) -> None:
            super().__init__(
                vars=_pymoo_vars(design_space),
                n_obj=len(objectives),
                n_ieq_constr=max(1, len(must_reqs)),
            )

        def _evaluate(self, x: dict[str, Any], out: dict[str, Any], *args: Any, **kw: Any) -> None:
            f, g = _evaluate_row(dict(x))
            out["F"] = f
            out["G"] = g

    algorithm = NSGA2(
        pop_size=pop_size,
        sampling=MixedVariableSampling(),
        mating=MixedVariableMating(eliminate_duplicates=MixedVariableDuplicateElimination()),
        eliminate_duplicates=MixedVariableDuplicateElimination(),
    )

    result = pymoo_minimize(
        _TradeProblem(),
        algorithm,
        ("n_gen", n_generations),
        seed=seed,
        verbose=verbose,
    )

    # pymoo returns a single dict (not a list) when the front collapses
    solutions = result.X if isinstance(result.X, (list, tuple)) else [result.X]
    if result.X is None:  # pragma: no cover - no feasible solution found
        return pd.DataFrame()
    import numpy as np

    if isinstance(result.X, np.ndarray):
        solutions = list(result.X)

    # Re-evaluate the nondominated set to attach full metrics
    rows: list[dict[str, Any]] = []
    for i, x in enumerate(solutions):
        row = dict(x)
        case_id = f"pareto_{i:05d}"
        try:
            arch = default_architecture_builder(row)
            metrics = evaluate_case(arch, scenario, requirements, case_id=case_id)
        except Exception as e:  # pragma: no cover - survived search but fails now
            metrics = {"meta.case_id": case_id, "meta.error": f"{type(e).__name__}: {e}"}
        rows.append({"case_id": case_id, **row, **metrics})

    return pd.DataFrame(rows)
