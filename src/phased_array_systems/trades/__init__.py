"""Trade study tools: DOE, batch evaluation, Pareto analysis, sensitivity, optimization."""

from phased_array_systems.trades.design_space import DesignSpace, DesignVariable
from phased_array_systems.trades.doe import generate_doe
from phased_array_systems.trades.optimization import OptimizationResult, optimize_design
from phased_array_systems.trades.pareto import extract_pareto, filter_feasible, rank_pareto
from phased_array_systems.trades.runner import BatchRunner
from phased_array_systems.trades.sensitivity import (
    compute_sensitivity_coefficients,
    oat_sensitivity,
)

__all__ = [
    "DesignSpace",
    "DesignVariable",
    "generate_doe",
    "BatchRunner",
    "extract_pareto",
    "filter_feasible",
    "rank_pareto",
    "oat_sensitivity",
    "compute_sensitivity_coefficients",
    "optimize_design",
    "OptimizationResult",
]
