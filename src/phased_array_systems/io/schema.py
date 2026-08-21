"""Configuration schema definitions using Pydantic."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from phased_array_systems.architecture import (
    Architecture,
    ArrayConfig,
    CostConfig,
    RFChainConfig,
)
from phased_array_systems.requirements import Requirement, RequirementSet
from phased_array_systems.scenarios import CommsLinkScenario, RadarDetectionScenario
from phased_array_systems.types import ComparisonOp, Severity


class RequirementConfig(BaseModel):
    """Configuration for a single requirement."""

    id: str
    name: str
    metric_key: str
    op: ComparisonOp
    value: float
    units: str | None = None
    severity: Severity = "must"

    def to_requirement(self) -> Requirement:
        """Convert to Requirement object."""
        return Requirement(
            id=self.id,
            name=self.name,
            metric_key=self.metric_key,
            op=self.op,
            value=self.value,
            units=self.units,
            severity=self.severity,
        )


class DesignVariableConfig(BaseModel):
    """Configuration for a design variable in DOE studies."""

    name: str = Field(description="Variable name (e.g., 'array.nx')")
    type: Literal["int", "float", "categorical"] = "float"
    low: float | None = Field(default=None, description="Lower bound")
    high: float | None = Field(default=None, description="Upper bound")
    values: list[Any] | None = Field(default=None, description="Categorical values")


class DOEConfig(BaseModel):
    """Configuration for Design of Experiments."""

    method: Literal["grid", "random", "lhs"] = "lhs"
    n_samples: int = Field(default=100, ge=1, description="Number of samples")
    seed: int | None = Field(default=None, description="Random seed")
    variables: list[DesignVariableConfig] = Field(default_factory=list)


class StudyConfig(BaseModel):
    """Top-level configuration for a study.

    Supports both single-case evaluation and DOE trade studies.

    Example YAML:
        ```yaml
        name: "Comms Array Study"
        architecture:
          array:
            nx: 8
            ny: 8
            dx_lambda: 0.5
          rf:
            tx_power_w_per_elem: 1.0
        scenario:
          type: comms
          freq_hz: 10e9
          bandwidth_hz: 10e6
          range_m: 100e3
          required_snr_db: 10.0
        requirements:
          - id: REQ-001
            name: Minimum EIRP
            metric_key: eirp_dbw
            op: ">="
            value: 40.0
        ```
    """

    name: str = Field(default="Unnamed Study", description="Study name")
    version: str = Field(default="1.0", description="Config version")

    # Architecture configuration
    architecture: Architecture | None = None
    array: ArrayConfig | None = Field(default=None, description="Array config (shorthand)")
    rf: RFChainConfig | None = Field(default=None, description="RF config (shorthand)")
    cost: CostConfig | None = Field(default=None, description="Cost config (shorthand)")

    # Scenario configuration
    scenario: dict[str, Any] | None = Field(default=None, description="Scenario definition")

    # Antenna evaluation method
    antenna_fidelity: Literal["analytic", "pattern"] | None = Field(
        default=None,
        description="Antenna method: 'analytic' (closed-form), 'pattern' "
        "(pattern-cut simulation), None (dispatch on library availability)",
    )

    # Requirements
    requirements: list[RequirementConfig] = Field(default_factory=list)

    # DOE configuration (optional, for trade studies)
    doe: DOEConfig | None = None

    # Output configuration
    output_dir: str = Field(default="./results", description="Output directory")
    output_format: Literal["parquet", "csv", "json"] = "parquet"

    def get_architecture(self) -> Architecture:
        """Get the Architecture object, building from shorthand if needed."""
        if self.architecture is not None:
            return self.architecture

        # Build from shorthand configs
        array = self.array or ArrayConfig(nx=8, ny=8)
        rf = self.rf or RFChainConfig(tx_power_w_per_elem=1.0)
        cost = self.cost or CostConfig()

        return Architecture(array=array, rf=rf, cost=cost, name=self.name)

    def get_scenario(self) -> CommsLinkScenario | RadarDetectionScenario | None:
        """Get the Scenario object from config."""
        if self.scenario is None:
            return None

        scenario_dict = self.scenario.copy()
        scenario_type = scenario_dict.pop("type", "comms")

        if scenario_type == "comms":
            return CommsLinkScenario(**scenario_dict)
        elif scenario_type == "radar":
            return RadarDetectionScenario(**scenario_dict)
        else:
            raise ValueError(f"Unknown scenario type: {scenario_type}")

    def get_requirement_set(self) -> RequirementSet:
        """Get RequirementSet from config."""
        req_set = RequirementSet(name=f"{self.name} Requirements")
        for req_config in self.requirements:
            req_set.add(req_config.to_requirement())
        return req_set
