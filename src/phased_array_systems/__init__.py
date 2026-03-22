"""
phased-array-systems: Phased array antenna system design, optimization, and visualization.

This package implements an MBSE/MDAO workflow for phased array system design:
requirements -> architecture -> analytical models -> trade studies -> Pareto selection -> reporting.
"""

from phased_array_systems.__about__ import __version__

# Architecture configs
from phased_array_systems.architecture import (
    Architecture,
    ArrayConfig,
    CostConfig,
    DigitalConfig,
    ReliabilityConfig,
    RFChainConfig,
)

# Evaluation
from phased_array_systems.evaluate import (
    evaluate_case,
    evaluate_case_with_report,
    evaluate_config,
)

# I/O
from phased_array_systems.io import (
    export_results,
    load_config,
    load_results,
)

# Requirements
from phased_array_systems.requirements import (
    Requirement,
    RequirementSet,
    VerificationReport,
)

# Scenarios
from phased_array_systems.scenarios import (
    CommsLinkScenario,
    RadarDetectionScenario,
)

# Trade studies and optimization
from phased_array_systems.trades import (
    BatchRunner,
    DesignSpace,
    OptimizationResult,
    extract_pareto,
    generate_doe,
    optimize_design,
)

__all__ = [
    "__version__",
    # Architecture
    "Architecture",
    "ArrayConfig",
    "CostConfig",
    "DigitalConfig",
    "ReliabilityConfig",
    "RFChainConfig",
    # Scenarios
    "CommsLinkScenario",
    "RadarDetectionScenario",
    # Requirements
    "Requirement",
    "RequirementSet",
    "VerificationReport",
    # Evaluation
    "evaluate_case",
    "evaluate_case_with_report",
    "evaluate_config",
    # Trades
    "BatchRunner",
    "DesignSpace",
    "OptimizationResult",
    "extract_pareto",
    "generate_doe",
    "optimize_design",
    # I/O
    "export_results",
    "load_config",
    "load_results",
]
