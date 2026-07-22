"""Cost models for phased array systems."""

from typing import Any

from phased_array_systems.architecture import Architecture
from phased_array_systems.types import MetricsDict, Scenario


class CostModel:
    """Parametric cost model for phased array systems.

    Computes recurring and non-recurring costs based on
    array size and cost parameters.

    Cost Equations:
        Recurring_cost = n_elements * cost_per_element
        Total_cost = Recurring_cost + NRE + Integration

    Attributes:
        name: Model block name for identification
    """

    name: str = "cost"

    def evaluate(
        self,
        arch: Architecture,
        scenario: Scenario,
        context: dict[str, Any],
    ) -> MetricsDict:
        """Evaluate cost metrics.

        Args:
            arch: Architecture configuration
            scenario: Scenario (unused for basic cost model)
            context: Additional context (unused)

        Returns:
            Dictionary with cost metrics:
                - recurring_cost_usd: Element-based recurring cost (USD)
                - nre_usd: Non-recurring engineering cost (USD)
                - integration_cost_usd: System integration cost (USD)
                - total_cost_usd: Total system cost (USD)
                - cost_per_element_usd: Cost per element (USD)
                - n_elements: Number of elements
        """
        n_elements = arch.array.n_elements
        cost_per_elem = arch.cost.cost_per_elem_usd
        nre = arch.cost.nre_usd
        integration = arch.cost.integration_cost_usd

        # Recurring cost (scales with elements)
        recurring_cost = n_elements * cost_per_elem

        # Total cost
        total_cost = recurring_cost + nre + integration

        return {
            "recurring_cost_usd": recurring_cost,
            "nre_usd": nre,
            "integration_cost_usd": integration,
            "total_cost_usd": total_cost,
            "cost_per_element_usd": cost_per_elem,
            "cost_usd": total_cost,  # Canonical metric name
            "n_elements": n_elements,
        }


def compute_cost_per_watt(total_cost_usd: float, rf_power_w: float) -> float:
    """Compute cost per Watt of RF power.

    Args:
        total_cost_usd: Total system cost (USD)
        rf_power_w: RF output power (W)

    Returns:
        Cost per Watt (USD/W)
    """
    if rf_power_w <= 0:
        return float("inf")
    return total_cost_usd / rf_power_w
