"""Type aliases and protocols for the phased-array-systems package."""

from typing import Any, Literal, Protocol, runtime_checkable

# Type aliases for metric dictionaries
MetricsDict = dict[str, float | int | str | bool | None]

# Comparison operators for requirements
ComparisonOp = Literal[">=", "<=", "==", ">", "<"]

# Severity levels for requirements
Severity = Literal["must", "should", "nice"]

# Geometry types supported by phased-array-modeling
GeometryType = Literal["rectangular", "circular", "triangular"]

# Path loss model types
PathLossModel = Literal["fspl"]

# DOE sampling methods
SamplingMethod = Literal["grid", "random", "lhs"]

# Optimization directions
OptimizeDirection = Literal["minimize", "maximize"]


@runtime_checkable
class Scenario(Protocol):
    """Protocol for scenario objects (comms, radar, etc.)."""

    freq_hz: float


@runtime_checkable
class ModelBlock(Protocol):
    """Protocol for model blocks that evaluate architecture/scenario combinations.

    All model blocks must implement evaluate() and return a flat metrics dictionary.
    """

    name: str

    def evaluate(self, arch: Any, scenario: Scenario, context: dict[str, Any]) -> MetricsDict:
        """Evaluate the model and return metrics.

        Args:
            arch: Architecture configuration object
            scenario: Scenario configuration object
            context: Additional context (e.g., results from other models)

        Returns:
            Dictionary of metric_name -> value pairs
        """
        ...
